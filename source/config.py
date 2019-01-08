# encoding: utf-8
# author: 'Marko Čibej'
"""
config.py
"""
__author__ = 'Marko Čibej'

import importlib.resources
import yaml
from copy import deepcopy
from typing import Union, List, Any


def dict_merge(target: dict, source: dict):
    """
    Recursively merges values from source into target.
    stolen from https://github.com/halfak/yamlconf
    """
    for key in source:
        if key in target and isinstance(target[key], dict) and isinstance(source[key], dict):
            dict_merge(target[key], source[key])
        else:
            target[key] = deepcopy(source[key])


def load_yaml(file_name: str = None, resource: str = None, package: str = None) -> dict:
    """
    Get the configuration and run it through yaml.
    If a filename is given, the configuration is loaded from that file.
    If a resource name is given, the configuration is read from a resource located in defined package.
    If both a filename and a resource are given, the resource is ignored.

    :param file_name: the name of the file
    :param resource: the name of the resource
    :param package: the name of the package or a ModuleType, i.e. importlib.resources.Package
    """
    #
    if file_name is not None:
        with open(file_name, 'r', encoding='utf-8') as f:
            yaml_string = f.read()
    else:
        with importlib.resources.open_text(package, resource) as r:
            yaml_string = r.read()

    the_map = yaml.load(yaml_string)

    if not isinstance(the_map, dict):
        raise YcError('Yaml source should map to a dictionary {}'.format(the_map))

    return the_map


class YcError(Exception):
    pass


class YamlConfig:
    """
    Contains the current configuration parameters.
    """
    maps: dict
    config_file_name: str
    patches: List

    def __init__(self, file_name: str = None, resource: str = None, package: str = None):
        """
        Loads the starting configuration.

        Essentially sets up an empty object, defaults resource to 'config.yaml' and package to __name__ + '.assets',
        ten passes the loading to patch(). No exceptions are handled, we shouldn't make assumptions about the
        caller's intents.

        :param file_name: see load_config
        :param resource: see load_config
        :param package: see load_config
        """
        self.patches = []
        self.maps = {}

        if file_name is not None:
            self.patch(file_name=file_name)
        if resource is None:
            resource = 'config.yaml'
        if package is None:
            package = __name__ + '.assets'

        self.patch(resource=resource, package=package)
        self.validate()

    def validate(self):
        """
        Run validity checks on the configuration map. This is meant to be overridden in subclass.
        Raise an exception if validation fails.
        """
        if 'steps' not in self.maps or not isinstance(self.maps['steps'], dict):
            raise YcError('Configuration.load, missing steps section, or section is not a map')

    def patch(self, file_name: str = None, resource: str = None, package: str = None,
              the_patch: dict = None, branch: str = None):
        """
        Recursively load the configuration from a file or a resource or an explicitly given source.
        Store the patch parameters.

        :param file_name: see load_yaml
        :param resource: see load_yaml
        :param package: when there are includes to process and package is not None, nested loads use the same package.
        :param the_patch: a source dict if it is given explicitly
        :param branch: a dot-separated address of the branch where the patch is to be applied
        """

        target = self.maps
        if branch is not None:
            for key in branch.split('.'):
                if key in target:
                    target = target[key]
                else:
                    raise YcError('Cannot locate branch {}'.format(branch))

        if the_patch is None:
            the_patch = load_yaml(file_name, resource, package)
            if file_name is not None:
                self.patches.append({'type': 'file', 'file-name': file_name, 'branch': branch})
            else:
                self.patches.append({'type': 'resource', 'resource': resource, 'package': package, 'branch': branch})
        else:
            self.patches.append({'type': 'patch', 'branch': branch})

        dict_merge(target, the_patch)

        if '__INCLUDE__' in target:
            for sub_branch, location in target['__INCLUDE__'].items():
                if file_name is not None:
                    self.patch(file_name=location, branch=branch + '.' + sub_branch)
                else:
                    self.patch(resource=location, package=package, branch=branch + '.' + sub_branch)
            del target['__INCLUDE__']

    def get_section(self, section: str, must_exist=False) -> Any:
        """
        Get a section of the configuration, potentially many levels deep.

        :param section: a section name or an array of section names, the path to the section sought
        :param must_exist: whether the method throws an exception if the section is not found
        :return: the section found or None
        """
        found = self.maps
        for s in section.split('.'):
            if s in found:
                found = found[s]
            else:
                found = None
                break

        if must_exist and found is None:
            raise YcError('Configuration.get_section, section {} not found'.format(section))

        return found

    def get_value(self, section: str, key: str, default=None) -> Any:
        """
        Get a  parameter within a section.

        :param section: the path to the section
        :param key: the key of the section
        :param default: the default value, if the section or the key is not found
        :return: the value found or default
        """
        sect = self.get_section(section)
        if sect is not None:
            if key in sect:
                return sect[key]

        return default

    def get_rule_set(self, step: str, key: str) -> Union[str, dict]:
        """
        Get a rule set for a processing step.

        :param step: the step for which to retrieve the rule set
        :param key: rule set key
        :return: a dictionary containing the rules
        """
        return self.get_section('.'.join(['steps', step, 'rules', key]), True)

    def get_parameter(self, step: str, key: str, default=None) -> Any:
        """
        Get a parameter for the processing step. If the parameter is not defined, return the default.

        :param step: the step for which to retrieve the parameter
        :param key: parameter key
        :param default: the value returned if the parameter is undefined
        :return: the parameter values
        """
        return self.get_value('.'.join(['steps', step, 'parameters']), key, default)

    def set_parameter(self, step: str, key: str, value: Any) -> Any:
        """
        Set a parameter, to permit on-the-fly reconfiguration. If the appropriate parameters section doesn't exist,
        an exception is thrown.

        :param step: the step for which to retrieve the parameter
        :param key: parameter key
        :param value: the new value of the parameter
        :return: the previous value of the parameter, if it exists
        """
        param_section = self.get_section('.'.join(['steps', step, 'parameters']), True)
        old_value = param_section[key] if key in param_section else None
        param_section[key] = value
        return old_value

    def set_global(self, param: str, value: Any) -> Any:
        """
        Set the value of a global parameter.
        :param param: the parameter name
        :param value: the parameter value
        :return: the previous value of the parameter, if any
        """
        previous = self.maps['GLOBAL'][param] if param in self.maps['GLOBAL'] else None
        self.maps['GLOBAL'][param] = value
        return previous

    def get_global(self, param: str, default: Any = None) -> Any:
        """
        Retrieve the value of a global parameter.
        :param param: the parameter name
        :param default: the default value; if it is None and if the parameter is not present, an exception is raised
        :return: the value of the parameter or the default
        """
        if param not in self.maps['GLOBAL'] and default is None:
            raise YcError('Configuration.get_global, parameter {} not set and no default given'.format(param))
        return self.maps['GLOBAL'][param] if param in self.maps['GLOBAL'] else default
