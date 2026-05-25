"""
MLOps Tracker
Integrates with MLflow to track experiments, hyperparameters, and results (Sharpe, IC).
"""
import mlflow
import yaml
import logging

class ExperimentTracker:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)["mlops"]
            
        mlflow.set_tracking_uri(self.config["mlflow_uri"])
        mlflow.set_experiment(self.config["experiment_name"])
        logging.info(f"Connected to MLFlow at {self.config['mlflow_uri']}")

    def start_run(self, run_name: str):
        mlflow.start_run(run_name=run_name)

    def log_params(self, params: dict):
        mlflow.log_params(params)

    def log_metrics(self, metrics: dict):
        """
        Log metrics like:
        - Information Coefficient (IC)
        - Rank IC
        - Sharpe Ratio
        - Max Drawdown
        """
        mlflow.log_metrics(metrics)

    def log_model(self, model, artifact_path="model"):
        mlflow.sklearn.log_model(model, artifact_path) # Example for sklearn compatible APIs

    def end_run(self):
        mlflow.end_run()

if __name__ == "__main__":
    # Example usage
    # tracker = ExperimentTracker()
    # tracker.start_run("lightgbm_alpha_158")
    # tracker.log_params({"learning_rate": 0.05, "max_depth": 8})
    # tracker.log_metrics({"IC": 0.045, "Sharpe": 1.8})
    # tracker.end_run()
    pass
