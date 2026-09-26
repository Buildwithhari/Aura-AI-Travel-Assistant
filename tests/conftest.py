import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["LLM_PROVIDER"] = "custom"        # tests never call a real LLM
os.environ["USE_MBERT"] = "false"
os.environ.setdefault("LLM_REPHRASE", "true")
