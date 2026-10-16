import antenna_bench.gr_metrics as metrics

class blk(metrics.BurstReceiver):
    def __init__(self, rate_index=2, correct_cfo=True, pilot_tracking=True, report_path=""):
        super().__init__(rate_index, correct_cfo, pilot_tracking, report_path)
