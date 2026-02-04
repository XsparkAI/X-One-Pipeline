import threading
import time
import yaml
import importlib
import argparse
from client_server.model_server import ModelServer

def eval_function_decorator(policy_name, model_name, conda_env=None):
    """Load a specified function (e.g., get_model) from a policy module"""
    module = importlib.import_module(policy_name)
    return getattr(module, model_name)

def main(usr_args):
    """Main entry: load model, start server, run indefinitely"""
    # Extract basic arguments
    policy_name = usr_args.get("policy_name")
    port = usr_args.get("port")

    # Instantiate model
    get_model = eval_function_decorator(f"policy_lab.{policy_name}", "get_model")
    model = get_model(usr_args)

    # Start server in background thread
    server = ModelServer(model, port=port)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()

    # Keep main thread alive until KeyboardInterrupt
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        server.stop()
        thread.join()

def parse_args_and_config():
    """Parse CLI args and YAML config, merge overrides"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, help="Port for ModelServer (optional)")
    parser.add_argument("--config_path", type=str, required=True, help="Path to config YAML")
    parser.add_argument("--overrides", nargs=argparse.REMAINDER, help="Override config values")
    args = parser.parse_args()

    # Load base config
    with open(args.config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["port"] = args.port

    # Parse overrides: --key value pairs
    if args.overrides:
        it = iter(args.overrides)
        for key in it:
            val = next(it)
            cfg[key.lstrip("--")] = eval(val) if val.isnumeric() else val
    return cfg

if __name__ == "__main__":
    usr_args = parse_args_and_config()
    main(usr_args)