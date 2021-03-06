#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from torchelastic.tsm.driver.api import (
    Application,
    AppNotReRunnableException,
    AppState,
    Container,
    DescribeAppResponse,
    Resources,
    Role,
    RunMode,
    UnknownAppException,
)
from torchelastic.tsm.driver.local_scheduler import (
    LocalDirectoryImageFetcher,
    LocalScheduler,
)
from torchelastic.tsm.driver.standalone_session import StandaloneSession

from .test_util import write_shell_script


class Resource:
    SMALL = Resources(cpu=1, gpu=0, memMB=1024)
    MEDIUM = Resources(cpu=4, gpu=0, memMB=(4 * 1024))
    LARGE = Resources(cpu=16, gpu=0, memMB=(16 * 1024))


class StandaloneSessionTest(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp("StandaloneSessionTest")

        write_shell_script(self.test_dir, "touch.sh", ["touch $1"])
        write_shell_script(self.test_dir, "fail.sh", ["exit 1"])
        write_shell_script(self.test_dir, "sleep.sh", ["sleep $1"])

        self.image_fetcher = LocalDirectoryImageFetcher()
        self.scheduler = LocalScheduler(self.image_fetcher)

        # resource ignored for local scheduler; adding as an example
        self.test_container = Container(image=self.test_dir).require(Resource.SMALL)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_run(self):
        test_file = os.path.join(self.test_dir, "test_file")
        session = StandaloneSession(
            name="test_session", scheduler=self.scheduler, wait_interval=1
        )
        role = Role(name="touch").runs("touch.sh", test_file).on(self.test_container)
        app = Application("name").of(role)

        app_id = session.run(app)
        self.assertEqual(AppState.SUCCEEDED, session.wait(app_id).state)

    def test_attach(self):
        session1 = StandaloneSession(name="test_session1", scheduler=self.scheduler)
        role = Role(name="sleep").runs("sleep.sh", "60").on(self.test_container)
        app = Application("sleeper").of(role)

        app_id = session1.run(app)

        session2 = StandaloneSession(name="test_session2", scheduler=self.scheduler)
        session2.attach(app_id)

        self.assertEqual(AppState.RUNNING, session2.status(app_id).state)
        session2.stop(app_id)
        self.assertEqual(AppState.CANCELLED, session2.status(app_id).state)

    def test_attach_and_run(self):
        session1 = StandaloneSession(name="test_session1", scheduler=self.scheduler)
        test_file = os.path.join(self.test_dir, "test_file")
        role = Role(name="touch").runs("touch.sh", test_file).on(self.test_container)
        app = Application("touch_test_file").of(role)
        app_id = session1.run(app)

        session2 = StandaloneSession(name="test_session2", scheduler=self.scheduler)
        attached_app = session2.attach(app_id)
        with self.assertRaises(AppNotReRunnableException):
            session2.run(attached_app)

    def test_list(self):
        session = StandaloneSession(
            name="test_session", scheduler=self.scheduler, wait_interval=1
        )
        role = Role(name="touch").runs("sleep.sh", "1").on(self.test_container)
        app = Application("sleeper").of(role)

        num_apps = 4

        for _ in range(num_apps):
            # since this test validates the list() API,
            # we do not wait for the apps to finish so run the apps
            # in managed mode so that the local scheduler reaps the apps on exit
            session.run(app, mode=RunMode.MANAGED)

        apps = session.list()
        self.assertEqual(num_apps, len(apps))

    def test_evict_non_existent_app(self):
        # tests that apps previously run with this session that are finished and eventually
        # removed by the scheduler also get removed from the session after a status() API has been
        # called on the app

        scheduler = LocalScheduler(self.image_fetcher, cache_size=1)
        session = StandaloneSession(
            name="test_session", scheduler=scheduler, wait_interval=1
        )
        test_file = os.path.join(self.test_dir, "test_file")
        role = Role(name="touch").runs("touch.sh", test_file).on(self.test_container)
        app = Application("touch_test_file").of(role)

        # local scheduler was setup with a cache size of 1
        # run the same app twice (the first will be removed from the scheduler's cache)
        # then validate that the first one will drop from the session's app cache as well
        app_id1 = session.run(app)
        session.wait(app_id1)

        app_id2 = session.run(app)
        session.wait(app_id2)

        apps = session.list()

        self.assertEqual(1, len(apps))
        self.assertFalse(app_id1 in apps)
        self.assertTrue(app_id2 in apps)

    def test_status(self):
        session = StandaloneSession(
            name="test_session", scheduler=self.scheduler, wait_interval=1
        )
        role = Role(name="sleep").runs("sleep.sh", "60").on(self.test_container)
        app = Application("sleeper").of(role)
        app_id = session.run(app)
        self.assertEqual(AppState.RUNNING, session.status(app_id).state)
        session.stop(app_id)
        self.assertEqual(AppState.CANCELLED, session.status(app_id).state)

    def test_status_unknown_app(self):
        session = StandaloneSession(
            name="test_session", scheduler=self.scheduler, wait_interval=1
        )
        with self.assertRaises(UnknownAppException):
            session.status("unknown_app_id")

    def test_status_ui_url(self):
        app_id = "test_app"
        mock_scheduler = MagicMock()
        resp = DescribeAppResponse()
        resp.ui_url = "https://foobar"
        mock_scheduler.submit.return_value = app_id
        mock_scheduler.describe.return_value = resp

        session = StandaloneSession(
            name="test_ui_url_session", scheduler=mock_scheduler
        )
        role = Role("ignored").runs("/bin/echo").on(self.test_container)
        session.run(Application(app_id).of(role))
        status = session.status(app_id)
        self.assertEquals(resp.ui_url, status.ui_url)

    def test_wait_unknown_app(self):
        session = StandaloneSession(
            name="test_session", scheduler=self.scheduler, wait_interval=1
        )
        with self.assertRaises(UnknownAppException):
            session.wait("unknown_app_id")

    def test_stop_unknown_app(self):
        session = StandaloneSession(
            name="test_session", scheduler=self.scheduler, wait_interval=1
        )
        with self.assertRaises(UnknownAppException):
            session.stop("unknown_app_id")
