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
from typing import List, Any, Tuple
from bisect import insort


def dict_merge(target: dict, source: dict, changes: List, current_path: str):
    """
    Recursively merges values from source into target. Returns a list of point that were changed.
    :param target: the target dict into which the changes were merged
    :param source: the source of the changes
    :param changes: the list of actually changed branches
    :param current_path: the current concatenation of path elements, used for updating _changed_
    :return: the list of branches that were actually changed
    """
    for key in source:
        if key in target and isinstance(target[key], dict) and isinstance(source[key], dict):
            dict_merge(target[key], source[key], changes, key if current_path == '' else '.'.join([current_path, key]))
        else:
            target[key] = deepcopy(source[key])
            changes.append(current_path)


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
    patch_locations: List
    patch_list: List[dict]

    def __init__(self, file_name: str = None, resource: str = None, package: str = None, patch_dict: dict = None):
        """
        Sets up an empty object and loads the starting configuration.

        Exactly one initializer is used. If the dict is used if present; if not, the file is loaded. If that
        is not given, the resource is loaded. The resource name and location default to 'assets/config.yaml'.

        No exceptions are handled, we shouldn't make assumptions about the caller's intent.

        :param file_name: see patch()
        :param resource: see patch()
        :param package: see patch()
        :param patch_dict: see patch()
        """
        self.patch_locations = []
        self.patch_list = []
        self.maps = {}

        if patch_dict is not None:
            self.patch(patch_dict=patch_dict)
        elif file_name is not None:
            self.patch(file_name=file_name)
        else:
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
              patch_dict: dict = None, branch: str = None):
        """
        Recursively load the configuration from a file or a resource or an explicitly given source.
        Store the patch parameters.

        :param file_name: see load_yaml
        :param resource: see load_yaml
        :param package: when there are includes to process and package is not None, nested loads use the same package.
        :param patch_dict: a source dict if it is given explicitly
        :param branch: a dot-separated address of the branch where the patch is to be applied
        """

        target = self.maps
        if branch is not None:
            for key in branch.split('.'):
                if key in target:
                    target = target[key]
                else:
                    raise YcError('Cannot locate branch {}'.format(branch))
        else:
            branch = ''

        patch_location = len(self.patch_list)
        if patch_dict is not None:
            the_patch = patch_dict
            self.patch_list.append({'type': 'dict', 'branch': branch, 'changed': False, 'patch': the_patch})
        else:
            the_patch = load_yaml(file_name, resource, package)
            if file_name is not None:
                self.patch_list.append({'type': 'file', 'file-name': file_name,
                                        'branch': branch, 'changed': False, 'patch': the_patch})
            else:
                self.patch_list.append({'type': 'resource', 'resource': resource, 'package': package,
                                        'branch': branch, 'changed': False, 'patch': the_patch})

        changes = []
        dict_merge(target, the_patch, changes, branch)
        for change in changes:
            insort(self.patch_locations, (change, patch_location))

        if '__INCLUDE__' in target:
            includes = target['__INCLUDE__']
            del target['__INCLUDE__']
            for sub_branch, location in includes.items():
                if file_name is not None:
                    self.patch(file_name=location, branch=branch + '.' + sub_branch)
                else:
                    self.patch(resource=location, package=package, branch=(branch + '.' if branch else '') + sub_branch)

    def save(self, all_to_root: bool = False, file_name: str = None) -> List:
        """
        Saves changed values to the files where they came from. Elements from patches that are not
        :param all_to_root: ignore patched branches and save everything to the root file
        :param file_name: save to the named file rather than the original one; only applies to the root, unless
                          all_to_root is also set
        :return: the list of patches considered and
        """
        results = []
        for patch in self.patch_list:
            if patch['type'] == 'dict':
                results.append({'type': 'dict', 'branch': patch['branch'], 'changed': patch['changed'], 'saved': False})
            elif patch['type'] == 'resource':
                results.append({'type': 'resource', 'branch': patch['branch'], 'resource': patch['resource'],
                                'package': patch['package'], 'changed': patch['changed'], 'saved': False})
            else:
                if not patch['changed']:
                    results.append({'type': 'file', 'branch': patch['branch'], 'file-name': patch['file-name'],
                                    'changed': patch['changed'], 'saved': False})
                else:
                    try:
                        with open(file_name, 'w', encoding='utf-8') as f:
                            yaml.dump(patch['patch'], f)
                        results.append({'type': 'file', 'branch': patch['branch'], 'file-name': patch['file-name'],
                                        'changed': patch['changed'], 'saved': True})
                    except Exception as e:
                        results.append({'type': 'file', 'branch': patch['branch'], 'file-name': patch['file-name'],
                                        'changed': patch['changed'], 'saved': False, 'error': str(e)})
        return results

    def get_section(self, path: str, must_exist=False) -> dict:
        """
        Get a section of the configuration, potentially many levels deep.

        :param path: a section name or an array of section names, the path to the section sought
        :param must_exist: whether the method throws an exception if the section is not found
        :return: the section found or None
        """
        found = self.maps
        for s in path.split('.'):
            if s in found:
                found = found[s]
            else:
                found = None
                break

        if must_exist and (found is None or not isinstance(found, dict)):
            raise YcError('YamlConfig.get_section, path {} not found or not a dict'.format(path))

        return found

    def get_value(self, path: str, key: str, default=None) -> Any:
        """
        Get a  parameter within a section.

        :param path: the path to the section
        :param key: the key of the section
        :param default: the default value, if the section or the key is not found
        :return: the value found or default
        """
        branch = self.get_section(path)
        if branch is not None:
            if key in branch:
                return branch[key]

        return default

    def set_value(self, path: str, key: str, value: Any) -> Tuple[Any, bool]:
        """
        Changes the value of an existing parameter. The change is made in two locations, in self.maps which is
        the current, consolidated version of the configuration, and in the stored patch where the value originated.
        Raises an exception if the path is not found, or if the original patch is not found.

        The replacement must be a leaf value, i.e. not a dict -- to attach a dict, use patch().
        The original value must exist.

        :param path: the section where the parameter is to be found
        :param key: the parameter's key
        :param value: the new value
        :return: the previous value and whether the patch can be saved
        """
        if isinstance(value, dict):
            raise YcError('YamlConfig.setValue, replacement value for {} may not be a dict'.format(key))

        loc = len(self.patch_locations) + 1
        for loc, pair in enumerate(reversed(self.patch_locations)):
            if pair[0] == path[:len(pair[0])]:
                break
        loc = len(self.patch_locations) - loc - 1
        if loc != 0 and self.patch_locations[loc][0] != path:
            raise YcError('YamlConfig.get_patch, patch for path at {} not found'.format(path))

        patch = self.patch_list[self.patch_locations[loc][1]]
        prefix = patch['branch']
        if len(path) < len(prefix) or path[:len(prefix)] != prefix:
            raise YcError('YamlConfig.get_patch, branch prefix {} is not a prefix to path {}'.format(path, prefix))
        patch_node = patch['patch']
        if len(path) > len(prefix):
            for node in path[len(patch['branch']):].split('.'):
                if node not in patch_node:
                    raise YcError('YamlConfig.get_patch, unable to trace path at node {}'.format(node))
                patch_node = patch_node[node]
        patch_node[key] = value
        patch['changed'] = True

        section = self.get_section(path, True)
        previous, section[key] = section[key], value

        return previous, patch['type'] == 'file'

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

    def traverse_branch(self, path):
        """
        Begin iteration over members of a sub-dir.
        :param path: the path to the sub-dir
        :return: self
        """
        pass
