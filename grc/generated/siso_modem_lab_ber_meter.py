import antenna_bench.gr_metrics as metrics

class blk(metrics.BitErrorMeter):
    def __init__(self, report_path="", run_config=None):
        super().__init__(report_path, run_config)
