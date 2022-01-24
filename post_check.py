"""
network_test_job.py
Example multi-testscript job file
"""

__author__ = "Daniel Salazar"
__copyright__ = "Copyright (c) 2022, Daniel Salazar"
__contact__ = ["salazardaniels@gmail.com"]
__license__ = "MIT License"
__credits__ = ["Daniel Salazar"]
__version__ = 1.0

import os
import time
from datetime import datetime, timedelta
from pyats.easypy import Task

# compute the script path from this location
SCRIPT_PATH = os.path.dirname(__file__)


def main(runtime):
    """job file entrypoint"""
    # shared_dict = runtime.synchro.dict()


    # using Task class to create a two tasks
    task_1 = Task(testscript=os.path.join(SCRIPT_PATH, "interface_verifications.py"),
    runtime = runtime,
    taskid = "Interface",
    pre = "pre_check",
    post = "post_check",
    offline = False,
    )

    task_2 = Task(testscript = os.path.join(SCRIPT_PATH, "config_verifications.py"),
    runtime = runtime,
    taskid = "Config",
    pre = "pre_check",
    post = "post_check",
    offline = False,
    )

    # start both tasks simultaneously
    task_1.start()
    task_2.start()
    # wait for both tasks to finish
    task_1.wait()
    task_2.wait()