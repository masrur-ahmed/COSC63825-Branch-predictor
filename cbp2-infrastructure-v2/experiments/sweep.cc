// sweep.cc
// Runs several predictor configurations side by side over one trace and
// prints the MPKI of each.  Usage: sweep <trace file>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../src/branch.h"
#include "../src/trace.h"
#include "../src/predictor.h"
#include "../src/my_predictor.h"

// static "always taken" baseline
class taken_predictor : public branch_predictor {
public:
	branch_update u;
	branch_update *predict (branch_info &) {
		u.direction_prediction (true);
		return &u;
	}
};

// bimodal table alone (the local half of the Pentium M hybrid)
class bimodal_predictor : public branch_predictor {
public:
	branch_update u;
	branch_info bi;
	unsigned char tab[1<<PM_BIMODAL_BITS];
	bimodal_predictor (void) { memset (tab, 2, sizeof (tab)); }
	branch_update *predict (branch_info & b) {
		bi = b;
		u.direction_prediction (tab[b.address & ((1<<PM_BIMODAL_BITS)-1)] >> 1);
		return &u;
	}
	void update (branch_update *, bool taken, unsigned int) {
		if (!(bi.br_flags & BR_CONDITIONAL)) return;
		pm_predictor::train (&tab[bi.address & ((1<<PM_BIMODAL_BITS)-1)], taken);
	}
};

struct config {
	const char *name;
	branch_predictor *p;
	long long dmiss;
};

int main (int argc, char *argv[]) {
	if (argc != 2) {
		fprintf (stderr, "Usage: %s <trace file>\n", argv[0]);
		exit (1);
	}
	config c[] = {
		{ "always-taken",            new taken_predictor (), 0 },
		{ "bimodal-4K",              new bimodal_predictor (), 0 },
		{ "gshare-32K",              new gshare_predictor (), 0 },
		{ "pm-1way",                 new pm_predictor (12, 9, 6, 1, 0, PM_ALLOC_KEEP, false), 0 },
		{ "pm-2way",                 new pm_predictor (12, 9, 6, 2, 0, PM_ALLOC_KEEP, false), 0 },
		{ "pm-4way",                 new pm_predictor (12, 9, 6, 4, 0, PM_ALLOC_KEEP, false), 0 },
		{ "pm-2way-alloc-reset",     new pm_predictor (12, 9, 6, 2, 0, PM_ALLOC_RESET, false), 0 },
		{ "pm-2way-alloc-on-bimiss", new pm_predictor (12, 9, 6, 2, 0, PM_ALLOC_KEEP, true), 0 },
		{ "pm-2way-ip-shift4",       new pm_predictor (12, 9, 6, 2, 4, PM_ALLOC_KEEP, false), 0 },
		{ "pm-2way-improved",        new pm_predictor (12, 9, 6, 2, 0, PM_ALLOC_RESET, true), 0 },
		{ "pm-4way-improved",        new pm_predictor (12, 9, 6, 4, 0, PM_ALLOC_RESET, true), 0 },
	};
	int n = sizeof (c) / sizeof (c[0]);

	init_trace (argv[1]);
	for (;;) {
		trace *t = read_trace ();
		if (!t) break;
		for (int i = 0; i < n; i++) {
			branch_update *u = c[i].p->predict (t->bi);
			if (t->bi.br_flags & BR_CONDITIONAL)
				c[i].dmiss += u->direction_prediction () != t->taken;
			c[i].p->update (u, t->taken, t->target);
		}
	}
	end_trace ();

	for (int i = 0; i < n; i++) {
		printf ("%s\t%0.3f\n", c[i].name, 1000.0 * (c[i].dmiss / 1e8));
		delete c[i].p;
	}
	return 0;
}
