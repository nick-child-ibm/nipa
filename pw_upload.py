#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
#
# Copyright (C) 2019 Netronome Systems, Inc.

import configparser
import os
import time
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from core import NIPA_DIR
from core import log, log_open_sec, log_end_sec, log_init
from pw import Patchwork, PatchworkCheckState

# TODO: document

PW = None
CONFIG = None


def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


class PwTestResult:
    def __init__(self, test_name: str, root_dir: str, url: str):
        self.test = test_name
        self.url = url

        try:
            with open(os.path.join(root_dir, test_name, "retcode"), "r") as f:
                retcode = f.read()
                if retcode == "0":
                    self.state = PatchworkCheckState.SUCCESS
                elif retcode == "250":
                    self.state = PatchworkCheckState.WARNING
                else:
                    self.state = PatchworkCheckState.FAIL
        except FileNotFoundError:
            self.state = PatchworkCheckState.FAIL

        try:
            with open(os.path.join(root_dir, test_name, "desc"), "r") as f:
                self.desc = f.read()
        except FileNotFoundError:
            self.desc = "Link"


def _pw_upload_results(series_dir, pw, config):
    series = os.path.basename(series_dir)
    result_server = config.get('results', 'server', fallback='https://google.com')

    # Collect series checks first
    series_results = []
    for root, dirs, _ in os.walk(series_dir):
        for test in dirs:
            if is_int(test):
                continue

            tr = PwTestResult(test, series_dir, f"{result_server}/{series}/{test}")
            series_results.append(tr)

        break

    log(f"Found {len(series_results)} series results")

    for root, dirs, _ in os.walk(series_dir):
        for patch in dirs:
            if not is_int(patch):
                continue

            for tr in series_results:
                pw.post_check(patch=patch, name=tr.test, state=tr.state, url=tr.url, desc=tr.desc)

            patch_dir = os.path.join(root, patch)
            for _, test_dirs, _ in os.walk(patch_dir):
                for test in test_dirs:
                    tr = PwTestResult(test, patch_dir, f"{result_server}/{series}/{patch}/{test}")
                    pw.post_check(patch=patch, name=tr.test, state=tr.state, url=tr.url, desc=tr.desc)

                log(f"Patch {patch} - found {len(test_dirs)} results")
                break
        break

    os.mknod(os.path.join(series_dir, ".pw_done"))


def pw_upload_results(series_dir, pw, config):
    log_open_sec(f'Upload results for {os.path.basename(series_dir)}')
    try:
        _pw_upload_results(series_dir, pw, config)
    finally:
        log_end_sec()


def _initial_scan(results_dir, pw, config):
    for root, dirs, _ in os.walk(results_dir):
        for d in dirs:
            path = os.path.join(root, d)
            if not os.path.exists(os.path.join(path, '.tester_done')):
                log(f"Test for {d} not done")
                continue
            if os.path.exists(os.path.join(path, '.pw_done')):
                log(f"Already uploaded {d}")
                continue
            pw_upload_results(path, pw, config)
        break


def initial_scan(results_dir, pw, config):
    log_open_sec('Upload initial')
    try:
        _initial_scan(results_dir, pw, config)
    finally:
        log_end_sec()


def on_created(event):
    global PW, CONFIG

    series_dir = os.path.dirname(event.src_path)
    log('Async event for ' + event.src_path)
    if os.path.exists(os.path.join(series_dir, '.pw_done')):
        log(f"Already uploaded {os.path.basename(series_dir)}")
        return
    pw_upload_results(series_dir, PW, CONFIG)


def watch_scan(results_dir, pw, config):
    global PW, CONFIG

    PW = pw
    CONFIG = config

    event_handler = PatternMatchingEventHandler(patterns=['*.tester_done'],
                                                ignore_patterns=[],
                                                ignore_directories=True,
                                                case_sensitive=True)
    event_handler.on_created = on_created

    observer = Observer()
    observer.schedule(event_handler, results_dir, recursive=True)

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()


def main():
    # Init state
    config = configparser.ConfigParser()
    config.read(['nipa.config', 'pw.config', 'upload.config'])

    log_init(config.get('log', 'type', fallback='org'),
             config.get('log', 'file', fallback=os.path.join(NIPA_DIR,
                                                             "upload.org")))

    results_dir = config.get('results', 'dir',
                             fallback=os.path.join(NIPA_DIR, "results"))

    pw = Patchwork(config)

    # Initial walk
    initial_scan(results_dir, pw, config)
    # Watcher
    watch_scan(results_dir, pw, config)


if __name__ == "__main__":
    main()
