# Copyright © 2013-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""A collection of authentication and authorization functions and classes."""
import typing

from cornice.errors import Errors
from pyramid.threadlocal import get_current_registry


try:
    # Pyramid >= 2.0
    from pyramid.authorization import ALL_PERMISSIONS, Allow, DENY_ALL
except ImportError:
    # Pyramid < 2.0
    from pyramid.security import ALL_PERMISSIONS, Allow, DENY_ALL


if typing.TYPE_CHECKING:  # pragma: no cover
    import pyramid.request.Request  # noqa: 401


#
# Pyramid ACL factories
#
class ACLFactory(object):
    """Define an ACL factory base class to share the __init__()."""

    def __init__(self, request: 'pyramid.request.Request', context: None = None):
        """
        Initialize the Factory.

        Args:
            request: The current request.
            context: The request's context (unused).
        """
        self.request = request


class AdminACLFactory(ACLFactory):
    """Define the ACLs for the admin only views below."""

    def __acl__(self) -> list:
        """
        Generate our admin-only ACL.

        Returns:
            A list of ACLs that allow all permissions for the admin_groups defined in
                settings.
        """
        return [(Allow, 'group:' + group, ALL_PERMISSIONS) for group in
                self.request.registry.settings['admin_groups']] + \
               [DENY_ALL]


class PackagerACLFactory(ACLFactory):
    """Define an ACL factory for packagers."""

    def __acl__(self) -> list:
        """
        Generate an ACL for update submission.

        Returns:
            A list of ACLs that allow all permissions for the mandatory_packager_groups
                defined in settings.
        """
        groups = self.request.registry.settings['mandatory_packager_groups']
        return [
            (Allow, 'group:' + group, ALL_PERMISSIONS) for group in groups
        ] + [DENY_ALL]


class CorsOrigins(object):
    """
    Proxy-list class to load CORS config after scan-time.

    This should appear to behave just like a list, but it loads values from the
    pyramid configuration for its values.  AFAIK, we have to do things this way
    since Cornice expects its cors configuration to be present at import-time,
    but the configuration isn't available until later, at Pyramid scan-time.
    Luckily, Cornice doesn't iterate over that configuration until
    request-time, so we can load this then.

        >>> cors_origins_ro = CorsOrigins('cors_origins_ro')
        >>> cors_origins_ro[0]
        ['*']
        >>> cors_origins_rw = CorsOrigins('cors_origins_rw')
        >>> cors_origins_rw[0]
        ['bodhi.fedoraproject.org']
    """

    def __init__(self, name: str):
        """
        Initialize the CorsOrigins object.

        Args:
            name: The name of the setting for the CORS config.
        """
        self.name = name
        self.origins = None

    def initialize(self):
        """Initialize the self.origins list."""
        if self.origins is None:
            settings = get_current_registry().settings
            self.origins = settings.get(self.name, 'localhost').split(',')

    def __len__(self) -> int:
        """
        Return the number of items in the CORS list.

        Returns:
            The number of items in the CORS list.
        """
        if self.origins is None:
            self.initialize()
        return len(self.origins)

    def __getitem__(self, key: object) -> object:
        """
        Define the [] operator.

        Args:
            key: The key of the object being accessed.
        Returns:
            The value referenced by the key.
        """
        if self.origins is None:
            self.initialize()
        return self.origins[key]

    def __iter__(self) -> typing.Iterator:
        """
        Iterate the CORS config.

        Returns:
            An iterator over the list of items.
        """
        if self.origins is None:
            self.initialize()
        return iter(self.origins)

    def __contains__(self, item: object) -> bool:
        """
        Define the 'in' operator.

        Args:
            item: The item to look for in the list.
        Returns:
            True if item is in the CORS config, False if not.
        """
        if self.origins is None:
            self.initialize()
        return item in self.origins


cors_origins_ro = CorsOrigins('cors_origins_ro')
cors_origins_rw = CorsOrigins('cors_origins_rw')


class ProtectedRequest(object):
    """
    A proxy to the request object.

    The point here is that you can set 'errors' on this request, but they
    will be sent to /dev/null and hidden from cornice.  Otherwise, this
    object behaves just like a normal request object.
    """

    def __init__(self, real_request: 'pyramid.request.Request'):
        """
        Initialize the object to look a lot like the real_request, but hiding the errors.

        Args:
            real_request: The request we are trying to mimic, while hiding
                its errors.
        """
        # Hide errors added to this from the real request
        self.errors = Errors()
        # But proxy other attributes to the real request
        self.real_request = real_request
        for attr in ['db', 'registry', 'validated', 'buildinfo', 'user']:
            setattr(self, attr, getattr(self.real_request, attr))
