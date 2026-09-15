import os
import tempfile

os.environ["TRACEFORGE_DEMO_TESTING"] = "true"
os.environ["DEMO_REPORTS_DIR"] = tempfile.mkdtemp()
