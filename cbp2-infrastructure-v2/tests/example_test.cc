// example_test.cc
// Replays the simplified hybrid predictor example from the assignment
// handout (Appendix B) and checks every prediction against the handout's
// tables: 8-bit addresses, 4-bit GHR, 16-entry bimodal table indexed by
// address bits [5:2], 2-way global predictor with 4 sets and 2-bit tags.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../src/branch.h"
#include "../src/predictor.h"
#include "../src/my_predictor.h"

int main (void) {
	// bimodal index bits [5:2] -> pass address >> 2 with a 4-bit table
	pm_predictor p (4, 2, 2, 2, 0, PM_ALLOC_KEEP, false);

	// initial counter values used in the handout
	for (int i = 0; i < 16; i++) p.bimodal[i] = i % 4;
	for (int s = 0; s < 4; s++) {
		p.ctr[s * 2 + 0] = s;
		p.ctr[s * 2 + 1] = 3 - s;
	}

	const unsigned int b1 = 0x44, b2 = 0x6C, b3 = 0x90;
	struct { unsigned int addr; int taken; char local, global, final_; } rows[] = {
		// address, outcome, local, global ('-' = no hit), final  (rows 1-22)
		{b1,1,'N','-','N'}, {b3,1,'N','-','N'}, {b1,0,'T','-','T'}, {b2,0,'T','-','T'},
		{b3,1,'N','-','N'}, {b1,1,'N','T','T'}, {b3,1,'T','-','T'}, {b1,0,'T','-','T'},
		{b2,0,'T','-','T'}, {b3,1,'T','T','T'}, {b1,0,'N','T','T'}, {b2,1,'N','-','N'},
		{b1,0,'N','-','N'}, {b2,0,'T','N','N'}, {b3,1,'T','-','T'}, {b1,1,'N','T','T'},
		{b3,1,'T','-','T'}, {b1,0,'N','-','N'}, {b2,0,'N','-','N'}, {b3,1,'T','T','T'},
		{b1,1,'N','T','T'}, {b3,1,'T','-','T'},
	};

	int n = sizeof (rows) / sizeof (rows[0]), fails = 0, correct = 0;
	printf ("row addr  outcome local global final  check\n");
	for (int i = 0; i < n; i++) {
		branch_info bi;
		bi.address = rows[i].addr >> 2;
		bi.opcode = 0;
		bi.br_flags = BR_CONDITIONAL;
		pm_update *u = (pm_update *) p.predict (bi);

		char local = u->bimodal_prediction ? 'T' : 'N';
		char global = u->way < 0 ? '-' : (p.ctr[u->set * 2 + u->way] >> 1 ? 'T' : 'N');
		char final_ = u->direction_prediction () ? 'T' : 'N';
		bool ok = local == rows[i].local && global == rows[i].global && final_ == rows[i].final_;
		fails += !ok;
		correct += (final_ == 'T') == (bool) rows[i].taken;
		printf ("%3d 0x%02X  %-7s %-5c %-6c %-5c  %s\n", i + 1, rows[i].addr,
			rows[i].taken ? "T" : "NT", local, global, final_, ok ? "ok" : "MISMATCH");

		p.update (u, rows[i].taken, 0);
	}
	printf ("%d/%d rows match the handout, %d/%d final predictions correct\n",
		n - fails, n, correct, n);
	return fails ? 1 : 0;
}
