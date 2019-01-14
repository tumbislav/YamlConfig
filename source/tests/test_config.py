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
        conf = YamlConfig()  # load from the default location
        self.assertEqual(conf.patch_list[0]['type'], 'resource')
        self.assertEqual(conf.patch_list[0]['resource'], 'config.yaml')
        self.assertEqual(conf.patch_list[0]['package'], 'assets')
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

    def test_section_and_param(self):
        """
        General access to sections and values, without assumptions of how they are structured.
        """
        conf = YamlConfig(resource='config.yaml', package='tests.assets')
        self.assertRaises(YcError, conf.get_section, *('none.such', True))
        d = conf.get_section('steps.write.parameters', True)
        self.assertEqual(d, {'json-schema': 'schema.json'})
        self.assertEqual(conf.get_value('steps.write.parameters', 'json-schema'), 'schema.json')

    def test_set_value(self):
        """
        Test the changing of individual values.
        """
        conf = YamlConfig(patch_dict={'root': {'branch': {'value': 0}}})
        previous, updatable = conf.set_value('root.branch', 'value', 2)
        self.assertEqual(previous, 0)
        self.assertFalse(updatable)
        self.assertEqual(conf.get_value('root.branch', 'value'), 2)
        result = conf.save()
