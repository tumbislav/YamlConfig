# encoding: utf-8
"""
test_config.py

Part of the ucs_to_cro package.

Unit tests for the package.
"""
__author__ = 'Marko Čibej'

import unittest
from config import YamlConfig, YcError


class TestConfiguration(unittest.TestCase):

    def test_load_basic(self):
        """
        Test the basic loading of the configuration file.
        """
        YamlConfig()  # load from the default location
        self.assertRaises(FileNotFoundError, YamlConfig, 'no-such-file.yaml')  # missing file
        self.assertRaises(YcError, YamlConfig,
                          **{'resource': 'yaml-with-errors.yaml', 'package': 'tests.assets'})  # invalid yaml

    def test_load_nested(self):
        """
        Check that nested conf files are properly loaded and assembled.
        """
        conf = YamlConfig(resource='nested.yaml', package='tests.assets')
        self.assertTrue(conf.get_value('from.main', 'file', False))
        self.assertTrue(conf.get_value('from.sub', 'file', False))
        self.assertEqual(conf.get_value('from.other', 'file'), 'possibly')
        self.assertEqual(conf.get_value('from.other', 'not-a-file'), 'is no file')

    def test_global(self):
        """
        Access to the 'GLOBAL' section. nested.yaml does not have a GLOBAL section, so it must be created at load.
        """
        conf = YamlConfig(resource='config.yaml', package='tests.assets')
        conf.set_global('new-param', 3)
        self.assertEqual(conf.get_global('new-param'), 3)
        self.assertRaises(YcError, conf.get_global, 'some-other-param')

    def test_section_and_param(self):
        """
        General access to sections and values, without assumptions of how they are structured.
        """
        conf = YamlConfig(resource='config.yaml', package='tests.assets')
        self.assertRaises(YcError, conf.get_section, *('none.such', True))
        d = conf.get_section('steps.write.parameters', True)
        self.assertEqual(d, {'json-schema': 'schema.json'})
        self.assertEqual(conf.get_value('steps.write.parameters', 'json-schema'), 'schema.json')

    def test_steps(self):
        """
        Properly structured conf contains the following structure:
            {steps: {step1: {parameters: {parameter1: value1, ...}, rules: {rule_set_1: ..., ...}}}}
        YamlConfig has special methods for accessing these structures.
        """
        conf = YamlConfig(resource='config.yaml', package='tests.assets')
        self.assertEqual(conf.get_rule_set('load', 'archive-source'), '^LOG$')
        self.assertEqual(conf.get_parameter('load', 'separator'), '|')
        self.assertIsNone(conf.set_parameter('load', 'new-parameter', 33))
        self.assertEqual(conf.get_parameter('load', 'new-parameter'), 33)
