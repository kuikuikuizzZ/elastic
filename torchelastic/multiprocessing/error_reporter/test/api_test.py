#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from unittest.mock import Mock, patch

from torchelastic.multiprocessing.error_reporter.api import exec_fn, get_error


def sum_func(arg1: int, arg2: int) -> int:
    return arg1 + arg2


class ErrorReporterApiTest(unittest.TestCase):
    @patch("torchelastic.multiprocessing.error_reporter.api.get_signal_handler")
    def test_exec_fn(self, get_signal_handler_mock):
        signal_handler_mock = Mock()
        get_signal_handler_mock.return_value = signal_handler_mock
        res = exec_fn(sum_func, args=(1, 2))
        self.assertEqual(3, res)
        signal_handler_mock.configure.assert_called_once()

    @patch("torchelastic.multiprocessing.error_reporter.api.get_signal_handler")
    def test_get_error(self, get_signal_handler_mock):
        signal_handler_mock = Mock()
        get_signal_handler_mock.return_value = signal_handler_mock
        get_error(1234)
        signal_handler_mock.construct_error_message.assert_called_once()
