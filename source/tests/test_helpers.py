# encoding: utf-8
"""
test_helpers.py

Part of the ucs_to_cro package.

Helper functions for unit tests.
"""
__author__ = 'Marko Čibej'

import os
import random
import string
import pkg_resources
import shutil
from typing import List


def set_up(test_files: List[str]) -> str:
    """
    Prepare the files for the test environment.
    :param test_files: the list of files to copy
    :return: the name of the test scratch directory
    """
    work_dir = os.path.join(os.getenv('TEST_SCRATCH'), ''.join(random.choices(string.ascii_lowercase, k=16)))
    os.makedirs(work_dir)
    for fn in test_files:
        dir_name, path_name = os.path.split(fn)
        target_dir = os.path.join(work_dir, dir_name)
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir)
        full_name = pkg_resources.resource_filename(__name__, 'assets/' + fn)
        shutil.copyfile(full_name, os.path.join(work_dir, fn))
    return work_dir


def tear_down(work_dir: str):
    """
    Clean up the test scratch environment.
    :param work_dir: the working directory.
    """
    shutil.rmtree(work_dir)
