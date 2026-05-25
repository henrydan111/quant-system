import sys
import os
from pathlib import Path
import qlib
from qlib.workflow import R
import pandas as pd
import matplotlib.pyplot as plt

# Add project root and src to sys.path
project_root = str(Path(os.path.abspath(__file__)).parent.parent.parent)
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

qlib_data_dir = os.path.join(project_root, "data", "qlib_format")

def main():
    print("Initializing Qlib...")
    qlib.init(provider_uri=qlib_data_dir, region="cn")

    # Set MLflow tracking URI to the workspace folder
    mlruns_dir = os.path.join(project_root, "workspace", "mlruns")
    R.set_uri(f"file:///{mlruns_dir}")

    print("Fetching backtest records from MLflow...")
    # Get the experiment by name and find the latest finished recorder
    exp = R.get_exp(experiment_name="poc_experiment")
    recorders = exp.list_recorders(status="FINISHED")
    
    if not recorders:
        print("No finished recorders found!")
        return

    # Use the latest finished recorder
    recent_rec = list(recorders.values())[0]
    print(f"Loading artifact from recorder: {recent_rec.id}")

    try:
        # Load the daily report DataFrame from the Qlib tracking artifacts
        report_df = recent_rec.load_object("portfolio_analysis/report_normal_1day.pkl")
    except Exception as e:
        print(f"Failed to load portfolio analysis. Did you run poc.py first? Error: {e}")
        return

    print("Artifact loaded successfully. Generating comprehensive performance report...")
    
    # Extract returns
    strategy_returns = report_df['return']
    benchmark_returns = report_df['bench']

    # 1. Generate text performance metrics table
    from result_analysis.metrics import generate_performance_report
    perf_df = generate_performance_report(strategy_returns, benchmark_returns)
    print("\n--- Performance Metrics ---")
    print(perf_df.to_string())
    print("---------------------------\n")

    # 2. Generate comprehensive graphical plots
    from result_analysis.plotters import plot_comprehensive_report
    output_path = os.path.join(project_root, "workspace", "outputs", "backtest_result.png")
    
    # We load seaborn/matplotlib inside the plotter, so we just call the function
    plot_comprehensive_report(strategy_returns, benchmark_returns, save_path=output_path)
    
    print(f"Success! Comprehensive backtest visualization saved to: {output_path}")

if __name__ == "__main__":
    main()
