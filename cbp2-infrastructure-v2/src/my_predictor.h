// my_predictor.h
// This file contains a sample gshare_predictor class.
// It is a simple 32,768-entry gshare with a history length of 15.

class gshare_update : public branch_update {
public:
	unsigned int index;
};

class gshare_predictor : public branch_predictor {
public:
#define HISTORY_LENGTH	15
#define TABLE_BITS	15
	gshare_update u;
	branch_info bi;
	unsigned int history;
	unsigned char tab[1<<TABLE_BITS];

	gshare_predictor (void) : history(0) { 
		memset (tab, 0, sizeof (tab));
	}

	branch_update *predict (branch_info & b) {
		bi = b;
		if (b.br_flags & BR_CONDITIONAL) {
			u.index = 
				  (history << (TABLE_BITS - HISTORY_LENGTH)) 
				^ (b.address & ((1<<TABLE_BITS)-1));
			u.direction_prediction (tab[u.index] >> 1);
		} else {
			u.direction_prediction (true);
		}
		u.target_prediction (0);
		return &u;
	}

	void update (branch_update *u, bool taken, unsigned int target) {
		if (bi.br_flags & BR_CONDITIONAL) {
			unsigned char *c = &tab[((gshare_update*)u)->index];
			if (taken) {
				if (*c < 3) (*c)++;
			} else {
				if (*c > 0) (*c)--;
			}
			history <<= 1;
			history |= taken;
			history &= (1<<HISTORY_LENGTH)-1;
		}
	}
};

//
// Pentium M hybrid branch predictors
// This class implements a simple hybrid branch predictor based on the Pentium M branch outcome prediction units. 
// Instead of implementing the complete Pentium M branch outcome predictors, the class below implements a hybrid 
// predictor that combines a bimodal predictor and a two-way global predictor. 
//
// Organization (defaults follow the Pentium M diagram in the assignment):
//
//   Bimodal table : 4096 2-bit counters, index = IP[11:0]
//   Global table  : 512 sets x 2 ways, each way = {valid, 6-bit tag, 2-bit counter},
//                   plus one LRU bit per set
//                   HASH  = IP[14:0] XOR GHR[14:0]   (PIR and its hash are not modeled;
//                                                     a 15-bit global history register
//                                                     of conditional outcomes is used)
//                   index = HASH[14:6], tag = HASH[5:0]
//   Final         : global prediction on a global hit, bimodal prediction otherwise
//
// All sizes are constructor parameters so the same code can also run the
// simplified 4-bit example from the assignment handout (see tests/).

#define PM_BIMODAL_BITS	12	// 4096-entry bimodal table
#define PM_INDEX_BITS	9	// 512 sets in the global predictor
#define PM_TAG_BITS	6	// 6-bit partial tags
#define PM_WAYS		2	// 2-way global predictor (the assignment allows 2 instead of 4)
#define PM_ADDR_SHIFT	0	// IP bits feeding the hash start at bit 0

// what to do with the 2-bit counter of a newly allocated global entry
#define PM_ALLOC_RESET	0	// set it to weakly taken / weakly not taken
#define PM_ALLOC_KEEP	1	// keep the old counter value and train it (handout example)

// allocation policy defaults; the handout example uses PM_ALLOC_KEEP and
// allocates on every global miss
#define PM_ALLOC_COUNTER		PM_ALLOC_KEEP
#define PM_ALLOC_ON_BIMODAL_MISS	false

class pm_update : public branch_update {
public:
        unsigned int index;		// bimodal table index
        unsigned int set;		// global predictor set
        unsigned int tag;		// global predictor tag
        int way;			// way that hit in the global predictor, -1 on a miss
        bool bimodal_prediction;
};

class pm_predictor : public branch_predictor {
public:
        pm_update u;
        branch_info bi;

        // configuration
        int bimodal_bits, index_bits, tag_bits, ways, addr_shift;
        int alloc_counter;		// PM_ALLOC_RESET or PM_ALLOC_KEEP
        bool alloc_on_bimodal_miss;	// allocate only when the bimodal predictor was wrong

        // state
        unsigned int history;		// global history register (index_bits + tag_bits long)
        unsigned char *bimodal;		// [1 << bimodal_bits] 2-bit counters
        unsigned char *valid;		// [sets * ways]
        unsigned char *tags;		// [sets * ways]
        unsigned char *ctr;		// [sets * ways] 2-bit counters
        unsigned char *lru;		// [sets * ways] 0 = MRU ... ways-1 = LRU

        pm_predictor (int bimodal_bits = PM_BIMODAL_BITS, int index_bits = PM_INDEX_BITS,
                      int tag_bits = PM_TAG_BITS, int ways = PM_WAYS, int addr_shift = PM_ADDR_SHIFT,
                      int alloc_counter = PM_ALLOC_COUNTER, bool alloc_on_bimodal_miss = PM_ALLOC_ON_BIMODAL_MISS) :
                bimodal_bits(bimodal_bits), index_bits(index_bits), tag_bits(tag_bits),
                ways(ways), addr_shift(addr_shift), alloc_counter(alloc_counter),
                alloc_on_bimodal_miss(alloc_on_bimodal_miss), history(0) {
                int entries = (1 << index_bits) * ways;
                bimodal = new unsigned char[1 << bimodal_bits];
                valid = new unsigned char[entries];
                tags = new unsigned char[entries];
                ctr = new unsigned char[entries];
                lru = new unsigned char[entries];
                memset (bimodal, 2, 1 << bimodal_bits);	// weakly taken
                memset (valid, 0, entries);
                memset (tags, 0, entries);
                memset (ctr, 2, entries);
                for (int i = 0; i < entries; i++) lru[i] = ways - 1 - (i % ways);	// way 0 is LRU
        }

        ~pm_predictor (void) {
                delete [] bimodal;
                delete [] valid;
                delete [] tags;
                delete [] ctr;
                delete [] lru;
        }

        static void train (unsigned char *c, bool taken) {
                if (taken) {
                        if (*c < 3) (*c)++;
                } else {
                        if (*c > 0) (*c)--;
                }
        }

        // make way w the most recently used way of set s
        void touch (unsigned int s, int w) {
                unsigned char *l = &lru[s * ways];
                for (int i = 0; i < ways; i++)
                        if (l[i] < l[w]) l[i]++;
                l[w] = 0;
        }

        branch_update *predict (branch_info & b) {
                bi = b;
                if (b.br_flags & BR_CONDITIONAL) {
                        // bimodal (local) prediction
                        u.index = b.address & ((1 << bimodal_bits) - 1);
                        u.bimodal_prediction = bimodal[u.index] >> 1;

                        // global prediction: hash the IP with the global history
                        int hash_bits = index_bits + tag_bits;
                        unsigned int hash = ((b.address >> addr_shift) ^ history) & ((1 << hash_bits) - 1);
                        u.set = hash >> tag_bits;
                        u.tag = hash & ((1 << tag_bits) - 1);
                        u.way = -1;
                        for (int w = 0; w < ways; w++) {
                                int e = u.set * ways + w;
                                if (valid[e] && tags[e] == u.tag) {
                                        u.way = w;
                                        break;
                                }
                        }

                        // global hit overrides the bimodal prediction
                        if (u.way >= 0)
                                u.direction_prediction (ctr[u.set * ways + u.way] >> 1);
                        else
                                u.direction_prediction (u.bimodal_prediction);
                } else {
                        u.direction_prediction (true);
                }

                // branch target prediction is not implemented
                u.target_prediction (0);
                return &u;
        }

        void update (branch_update *bu, bool taken, unsigned int target) {
                if (!(bi.br_flags & BR_CONDITIONAL)) return;
                pm_update *pu = (pm_update *) bu;

                // the bimodal table is always trained
                train (&bimodal[pu->index], taken);

                if (pu->way >= 0) {
                        train (&ctr[pu->set * ways + pu->way], taken);
                        touch (pu->set, pu->way);
                } else if (!alloc_on_bimodal_miss || pu->bimodal_prediction != taken) {
                        // global miss: allocate an invalid way, or else the LRU way
                        int victim = 0;
                        for (int w = 0; w < ways; w++) {
                                int e = pu->set * ways + w;
                                if (!valid[e]) { victim = w; break; }
                                if (lru[e] > lru[pu->set * ways + victim]) victim = w;
                        }
                        int e = pu->set * ways + victim;
                        valid[e] = 1;
                        tags[e] = pu->tag;
                        if (alloc_counter == PM_ALLOC_RESET)
                                ctr[e] = taken ? 2 : 1;
                        else
                                train (&ctr[e], taken);
                        touch (pu->set, victim);
                }

                // shift the outcome into the global history register
                history = ((history << 1) | taken) & ((1 << (index_bits + tag_bits)) - 1);
        }
};

//
// Complete Pentium M branch predictors for extra credit
// This class implements the complete Pentium M branch prediction units. 
// It implements both branch target prediction and branch outcome predicton. 
class cpm_update : public branch_update {
public:
        unsigned int index;
};

class cpm_predictor : public branch_predictor {
public:
        cpm_update u;

        cpm_predictor (void) {
        }

        branch_update *predict (branch_info & b) {
            u.direction_prediction (true);
            u.target_prediction (0);
            return &u;
        }

        void update (branch_update *u, bool taken, unsigned int target) {
        }

};


