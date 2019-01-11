# encoding: utf-8
# author: 'Marko Čibej'
"""
config.py
"""
__author__ = 'Marko Čibej'

import importlib.resources
import yaml
from yaml.scanner import ScannerError
from copy import deepcopy
from typing import List, Any, Optional
from bisect import insort


def dict_merge(target: dict, source: dict, changes: List, current_path: str):
    """
    Recursively merges values from source into target. Returns a list of point that were changed.
    :param target: the target dict into which the changes were merged
    :param source: the source of the changes
    :param changed: the list of actually changed branches
    :param current_path: the current concatenation of path elements, used for updating _changed_
    :return: the list of branches that were actually changed
    """
    for key in source:
        if key in target and isinstance(target[key], dict) and isinstance(source[key], dict):
            dict_merge(target[key], source[key], changes, current_path + '.' + key)
        else:
            target[key] = deepcopy(source[key])
            changes.append(current_path + '.' + key)


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

    try:
        the_map = yaml.load(yaml_string)
    except yaml.scanner.ScannerError as e:
        raise YcError('load_yaml: yaml scanner error {}'.format(e))

    if not isinstance(the_map, dict):
        raise YcError('load_yaml: yaml source should map to a dictionary {}'.format(the_map))

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
            package = 'assets'

        self.patch(resource=resource, package=package)
        self.validate()

    def validate(self):
        """
        Run validity checks on the configuration map. This is meant to be overridden in subclass.
        Raise an exception if validation fails.
        """
        pass

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
                source = {'type': 'file', 'file-name': file_name}
            else:
                source = {'type': 'resource', 'resource': resource, 'package': package}
        else:
            source = {'type': 'patch'}

        changes = []
        dict_merge(target, the_patch, changes, branch)
        for change in changes:
            insort(self.patches, (change, source))

        if '__INCLUDE__' in target:
            includes = target['__INCLUDE__']
            del target['__INCLUDE__']
            for sub_branch, location in includes.items():
                if file_name is not None:
                    self.patch(file_name=location, branch=branch + '.' + sub_branch)
                else:
                    self.patch(resource=location, package=package,
                               branch=(branch + '.' if branch is not None else '') + sub_branch)

    def register_patch(self, branch, source):

    def save(self, all_to_root: bool = False, file_name: str = None) -> Optional[list]:
        """
        Saves changed values to the files where they came from. Elements from non
        :param all_to_root: ignore patched branches and save everything to the root file
        :param file_name: save to the named file rather than the original one; only applies to the root, unless
                          all_to_root is also set
        :return: the list of branches not saved, or None
        """
        self.patches.sort(key=lambda x: x[0])

        return None

    def get_section(self, section: str, must_exist=False) -> dict:
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

        if must_exist and (found is None or not isinstance(found, dict)):
            raise YcError('YamlConfig.get_section, section {} not found or not a dict'.format(section))

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

    def set_value(self, section: str, key: str, value: Any) -> Any:
        """
        Changes the value of an existing parameter. The replacement value can be anything, so this is a
        way to depen the structure without using patch.
        :param section: the section where the parameter is to be found
        :param key: the parameter's key
        :param value: the new value
        :return: the previous value, if any
        """
        pass

    def __iter__(self):
        """
        Identifies the object as an iterator. If no iteration is active, begins a depth-first traverse
        of self.maps
        :return: self
        """
        return self

    def __next__(self):
        """
        Get the next element of the current iteration.
        :return: the element
        """
        pass

    def branch(self, section):
        """
        Begin iteration over members of a sub-dir.
        :param section: the path to the sub-dir
        :return: self
        """
        pass

    def list(self, section):
        """
        Begin iteration over a list.
        :param section: the path to the list
        :return: self
        """
        pass
