#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""
RBAC (Role-Based Access Control) Decorators and Utilities

This module provides decorators and utility functions for enforcing
role-based access control in API endpoints.

Usage:
    from api.utils.rbac import require_admin, require_kb_permission

    @manager.route('/admin/users', methods=['GET'])
    @login_required
    @require_admin()
    async def list_all_users():
        # Only admin users can access this
        pass

    @manager.route('/kb/<kb_id>/documents', methods=['POST'])
    @login_required
    @require_kb_permission('create')
    async def upload_document(kb_id):
        # Only users with 'create' permission on kb_id can access this
        pass
"""

import inspect
import logging
from functools import wraps
from typing import Callable, List, Optional

from quart import request

from api.db.services.rbac_service import (
    PermissionService,
    UserGroupMemberService,
    UserGroupService,
    GroupKnowledgebasePermissionService
)
from api.utils.api_utils import get_json_result
from common.constants import RetCode


def require_admin():
    """
    Decorator that requires the current user to be an admin.

    This decorator checks if the current user belongs to any admin group.
    If not, it returns a 403 Forbidden response.

    Usage:
        @require_admin()
        async def admin_only_endpoint():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from api.apps import current_user

            if not current_user or not current_user.id:
                return get_json_result(
                    code=RetCode.UNAUTHORIZED,
                    message="Authentication required"
                )

            if not UserGroupMemberService.is_user_admin(current_user.id):
                return get_json_result(
                    code=RetCode.FORBIDDEN,
                    message="Admin access required"
                )

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper
    return decorator


def require_kb_permission(permission_type: str, kb_id_param: str = 'kb_id'):
    """
    Decorator that requires specific permission on a knowledge base.

    This decorator extracts the KB ID from request parameters and checks
    if the current user has the specified permission on that KB.

    Args:
        permission_type: One of 'read', 'update', 'delete', 'create'
        kb_id_param: Name of the parameter containing the KB ID
                    (can be in URL path, query string, or request body)

    Usage:
        @require_kb_permission('read')
        async def get_kb_documents(kb_id):
            pass

        @require_kb_permission('create', kb_id_param='knowledge_base_id')
        async def upload_document():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from api.apps import current_user

            if not current_user or not current_user.id:
                return get_json_result(
                    code=RetCode.UNAUTHORIZED,
                    message="Authentication required"
                )

            # Try to get kb_id from various sources
            kb_id = None

            # 1. Check URL path parameters (kwargs)
            if kb_id_param in kwargs:
                kb_id = kwargs[kb_id_param]

            # 2. Check query string
            if not kb_id:
                kb_id = request.args.get(kb_id_param)

            # 3. Check request body (for POST/PUT requests)
            if not kb_id and request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    data = await request.get_json(force=True, silent=True)
                    if data and isinstance(data, dict):
                        kb_id = data.get(kb_id_param)
                except Exception:
                    pass

            if not kb_id:
                return get_json_result(
                    code=RetCode.ARGUMENT_ERROR,
                    message=f"Missing required parameter: {kb_id_param}"
                )

            # Check permission
            has_permission = _check_kb_permission(
                current_user.id, kb_id, permission_type
            )

            if not has_permission:
                return get_json_result(
                    code=RetCode.FORBIDDEN,
                    message=f"Permission denied: you don't have '{permission_type}' access to this knowledge base"
                )

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper
    return decorator


def require_kb_list_permission(permission_type: str, kb_ids_param: str = 'kb_ids'):
    """
    Decorator that requires specific permission on multiple knowledge bases.

    Checks if the current user has the specified permission on ALL provided KBs.
    Useful for operations that involve multiple KBs like creating dialogs.

    Args:
        permission_type: One of 'read', 'update', 'delete', 'create'
        kb_ids_param: Name of the parameter containing the list of KB IDs

    Usage:
        @require_kb_list_permission('read')
        async def create_dialog():
            # Request body should contain kb_ids: ["kb1", "kb2"]
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from api.apps import current_user

            if not current_user or not current_user.id:
                return get_json_result(
                    code=RetCode.UNAUTHORIZED,
                    message="Authentication required"
                )

            # Try to get kb_ids from request body
            kb_ids = []
            if request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    data = await request.get_json(force=True, silent=True)
                    if data and isinstance(data, dict):
                        kb_ids = data.get(kb_ids_param, [])
                except Exception:
                    pass

            # If no kb_ids provided, allow (empty list means no KB restrictions)
            if not kb_ids:
                if inspect.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

            # Check permission on all KBs
            if not PermissionService.can_access_dialog_kbs(current_user.id, kb_ids):
                return get_json_result(
                    code=RetCode.FORBIDDEN,
                    message=f"Permission denied: you don't have '{permission_type}' access to one or more knowledge bases"
                )

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper
    return decorator


def _check_kb_permission(user_id: str, kb_id: str, permission_type: str) -> bool:
    """
    Internal helper to check if a user has a specific permission on a KB.

    Args:
        user_id: User ID
        kb_id: Knowledge base ID
        permission_type: One of 'read', 'update', 'delete', 'create'

    Returns:
        True if user has the permission, False otherwise
    """
    permission_checkers = {
        'read': PermissionService.can_read_kb,
        'update': PermissionService.can_update_kb,
        'delete': PermissionService.can_delete_kb,
        'create': PermissionService.can_create_in_kb,
    }

    checker = permission_checkers.get(permission_type)
    if not checker:
        logging.warning(f"Unknown permission type: {permission_type}")
        return False

    return checker(user_id, kb_id)


def get_user_permissions(user_id: str, kb_id: Optional[str] = None) -> dict:
    """
    Get permissions for a user.

    Args:
        user_id: User ID
        kb_id: Optional KB ID. If provided, returns permissions for that specific KB.
               If not provided, returns all permissions for the user.

    Returns:
        Dictionary with permission information
    """
    if kb_id:
        return PermissionService.get_user_kb_permissions(user_id, kb_id)
    else:
        return PermissionService.get_user_all_permissions(user_id)


def get_accessible_kbs(user_id: str, permission_type: str = 'read') -> List[str]:
    """
    Get list of KB IDs that a user can access.

    Args:
        user_id: User ID
        permission_type: One of 'read', 'update', 'delete', 'create'

    Returns:
        List of accessible KB IDs
    """
    return PermissionService.get_accessible_kb_ids(user_id, permission_type)


def is_admin(user_id: str) -> bool:
    """
    Check if a user is an admin.

    Args:
        user_id: User ID

    Returns:
        True if user is admin, False otherwise
    """
    return UserGroupMemberService.is_user_admin(user_id)


def filter_kbs_by_permission(
    user_id: str,
    kb_ids: List[str],
    permission_type: str = 'read'
) -> List[str]:
    """
    Filter a list of KB IDs to only include those the user has access to.

    Args:
        user_id: User ID
        kb_ids: List of KB IDs to filter
        permission_type: One of 'read', 'update', 'delete', 'create'

    Returns:
        Filtered list of KB IDs
    """
    if is_admin(user_id):
        return kb_ids

    accessible_kbs = set(get_accessible_kbs(user_id, permission_type))
    return [kb_id for kb_id in kb_ids if kb_id in accessible_kbs]


async def get_request_kb_id(kb_id_param: str = 'kb_id') -> Optional[str]:
    """
    Extract KB ID from request (URL params, query string, or body).

    Args:
        kb_id_param: Name of the KB ID parameter

    Returns:
        KB ID if found, None otherwise
    """
    # Check query string
    kb_id = request.args.get(kb_id_param)
    if kb_id:
        return kb_id

    # Check request body
    if request.method in ['POST', 'PUT', 'PATCH']:
        try:
            data = await request.get_json(force=True, silent=True)
            if data and isinstance(data, dict):
                return data.get(kb_id_param)
        except Exception:
            pass

    return None
