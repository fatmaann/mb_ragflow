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
RBAC (Role-Based Access Control) API Endpoints

This module provides API endpoints for managing:
- User groups
- Group memberships
- Knowledge base permissions

All group and permission management endpoints require admin access.
"""

from quart import request

from api.apps import login_required, current_user
from api.db.services.rbac_service import (
    UserGroupService,
    UserGroupMemberService,
    GroupKnowledgebasePermissionService,
    PermissionService
)
from api.db.services.user_service import UserService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.utils.api_utils import (
    get_json_result,
    get_request_json,
    server_error_response,
    get_data_error_result,
    validate_request
)
from api.utils.rbac import require_admin, is_admin
from common.constants import RetCode, StatusEnum


# ============================================================================
# Group Management Endpoints
# ============================================================================

@manager.route('/group/create', methods=['POST'])  # noqa: F821
@login_required
@require_admin()
@validate_request("name")
async def create_group():
    """
    Create a new user group.

    Request body:
        - name (str): Group name (required)
        - description (str): Group description (optional)
        - is_admin (bool): Whether this is an admin group (optional, default: false)

    Returns:
        Group object on success
    """
    try:
        req = await get_request_json()
        name = req.get("name", "").strip()
        description = req.get("description", "")
        is_admin_group = req.get("is_admin", False)

        if not name:
            return get_data_error_result(message="Group name cannot be empty")

        # Check if group with this name already exists
        existing = UserGroupService.get_by_name(name)
        if existing:
            return get_data_error_result(message=f"Group '{name}' already exists")

        group = UserGroupService.create_group(
            name=name,
            description=description,
            is_admin=is_admin_group
        )

        return get_json_result(data={
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "is_admin": group.is_admin
        })
    except Exception as e:
        return server_error_response(e)


@manager.route('/group/<group_id>', methods=['PUT'])  # noqa: F821
@login_required
@require_admin()
async def update_group(group_id):
    """
    Update a user group.

    Path parameters:
        - group_id: ID of the group to update

    Request body:
        - name (str): New group name (optional)
        - description (str): New description (optional)

    Note: is_admin cannot be changed after creation
    """
    try:
        req = await get_request_json()

        # Verify group exists
        success, group = UserGroupService.get_by_id(group_id)
        if not success:
            return get_data_error_result(message="Group not found")

        update_data = {}
        if "name" in req:
            name = req["name"].strip()
            if not name:
                return get_data_error_result(message="Group name cannot be empty")
            # Check for duplicate name (excluding current group)
            existing = UserGroupService.get_by_name(name)
            if existing and existing.id != group_id:
                return get_data_error_result(message=f"Group '{name}' already exists")
            update_data["name"] = name

        if "description" in req:
            update_data["description"] = req["description"]

        if update_data:
            UserGroupService.update_group(group_id, **update_data)

        # Return updated group
        success, updated_group = UserGroupService.get_by_id(group_id)
        return get_json_result(data={
            "id": updated_group.id,
            "name": updated_group.name,
            "description": updated_group.description,
            "is_admin": updated_group.is_admin
        })
    except Exception as e:
        return server_error_response(e)


@manager.route('/group/<group_id>', methods=['DELETE'])  # noqa: F821
@login_required
@require_admin()
async def delete_group(group_id):
    """
    Delete a user group.

    Path parameters:
        - group_id: ID of the group to delete

    Note: Admin groups and default groups cannot be deleted
    """
    try:
        success, group = UserGroupService.get_by_id(group_id)
        if not success:
            return get_data_error_result(message="Group not found")

        # Prevent deletion of admin groups
        if group.is_admin:
            return get_json_result(
                code=RetCode.FORBIDDEN,
                message="Cannot delete admin groups"
            )

        # Prevent deletion of default groups
        from api.db.db_models import DEFAULT_ADMIN_GROUP_NAME, DEFAULT_USER_GROUP_NAME
        if group.name in [DEFAULT_ADMIN_GROUP_NAME, DEFAULT_USER_GROUP_NAME]:
            return get_json_result(
                code=RetCode.FORBIDDEN,
                message="Cannot delete default system groups"
            )

        UserGroupService.delete_group(group_id)
        return get_json_result(data=True, message="Group deleted successfully")
    except Exception as e:
        return server_error_response(e)


@manager.route('/group/list', methods=['GET'])  # noqa: F821
@login_required
async def list_groups():
    """
    List user groups.

    For admin users: returns all groups
    For regular users: returns only groups they belong to

    Query parameters:
        - all (bool): If true and user is admin, return all groups
    """
    try:
        show_all = request.args.get('all', 'false').lower() == 'true'

        if is_admin(current_user.id) and show_all:
            groups = UserGroupService.get_all_groups()
        else:
            groups = UserGroupMemberService.get_user_groups(current_user.id)

        result = [{
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "is_admin": g.is_admin
        } for g in groups]

        return get_json_result(data=result)
    except Exception as e:
        return server_error_response(e)


# ============================================================================
# Group Membership Endpoints
# ============================================================================

@manager.route('/group/<group_id>/member', methods=['POST'])  # noqa: F821
@login_required
@require_admin()
@validate_request("user_id")
async def add_group_member(group_id):
    """
    Add a user to a group.

    Path parameters:
        - group_id: ID of the group

    Request body:
        - user_id (str): ID of the user to add
    """
    try:
        req = await get_request_json()
        user_id = req.get("user_id")

        # Verify group exists
        success, group = UserGroupService.get_by_id(group_id)
        if not success:
            return get_data_error_result(message="Group not found")

        # Verify user exists
        user = UserService.filter_by_id(user_id)
        if not user:
            return get_data_error_result(message="User not found")

        # Add user to group
        membership = UserGroupMemberService.add_user_to_group(user_id, group_id)

        return get_json_result(data={
            "membership_id": membership.id,
            "user_id": user_id,
            "group_id": group_id,
            "message": "User added to group successfully"
        })
    except Exception as e:
        return server_error_response(e)


@manager.route('/group/<group_id>/member/<user_id>', methods=['DELETE'])  # noqa: F821
@login_required
@require_admin()
async def remove_group_member(group_id, user_id):
    """
    Remove a user from a group.

    Path parameters:
        - group_id: ID of the group
        - user_id: ID of the user to remove
    """
    try:
        # Verify group exists
        success, group = UserGroupService.get_by_id(group_id)
        if not success:
            return get_data_error_result(message="Group not found")

        # Remove user from group
        UserGroupMemberService.remove_user_from_group(user_id, group_id)

        return get_json_result(data=True, message="User removed from group successfully")
    except Exception as e:
        return server_error_response(e)


@manager.route('/group/<group_id>/members', methods=['GET'])  # noqa: F821
@login_required
async def list_group_members(group_id):
    """
    List all members of a group.

    Path parameters:
        - group_id: ID of the group

    Note: Admin users can view any group's members.
          Regular users can only view members of groups they belong to.
    """
    try:
        # Verify group exists
        success, group = UserGroupService.get_by_id(group_id)
        if not success:
            return get_data_error_result(message="Group not found")

        # Check access: admin or member of the group
        if not is_admin(current_user.id):
            if not UserGroupMemberService.is_user_in_group(current_user.id, group_id):
                return get_json_result(
                    code=RetCode.FORBIDDEN,
                    message="You don't have access to view this group's members"
                )

        members = UserGroupMemberService.get_group_members(group_id)
        return get_json_result(data=members)
    except Exception as e:
        return server_error_response(e)


# ============================================================================
# Knowledge Base Permission Endpoints
# ============================================================================

@manager.route('/permission/kb', methods=['POST'])  # noqa: F821
@login_required
@require_admin()
@validate_request("group_id", "kb_id")
async def set_kb_permission():
    """
    Set permissions for a group on a knowledge base.

    Request body:
        - group_id (str): ID of the group
        - kb_id (str): ID of the knowledge base
        - can_read (bool): Read permission (default: false)
        - can_update (bool): Update permission (default: false)
        - can_delete (bool): Delete permission (default: false)
        - can_create (bool): Create permission (default: false)
    """
    try:
        req = await get_request_json()
        group_id = req.get("group_id")
        kb_id = req.get("kb_id")

        # Verify group exists
        success, group = UserGroupService.get_by_id(group_id)
        if not success:
            return get_data_error_result(message="Group not found")

        # Verify KB exists
        success, kb = KnowledgebaseService.get_by_id(kb_id)
        if not success:
            return get_data_error_result(message="Knowledge base not found")

        # Set permissions
        permission = GroupKnowledgebasePermissionService.set_permission(
            group_id=group_id,
            kb_id=kb_id,
            can_read=req.get("can_read", False),
            can_update=req.get("can_update", False),
            can_delete=req.get("can_delete", False),
            can_create=req.get("can_create", False)
        )

        return get_json_result(data={
            "id": permission.id,
            "group_id": permission.group_id,
            "kb_id": permission.kb_id,
            "can_read": permission.can_read,
            "can_update": permission.can_update,
            "can_delete": permission.can_delete,
            "can_create": permission.can_create
        })
    except Exception as e:
        return server_error_response(e)


@manager.route('/permission/kb/<permission_id>', methods=['PUT'])  # noqa: F821
@login_required
@require_admin()
async def update_kb_permission(permission_id):
    """
    Update a knowledge base permission.

    Path parameters:
        - permission_id: ID of the permission to update

    Request body:
        - can_read (bool): Read permission
        - can_update (bool): Update permission
        - can_delete (bool): Delete permission
        - can_create (bool): Create permission
    """
    try:
        req = await get_request_json()

        # Get existing permission
        success, permission = GroupKnowledgebasePermissionService.get_by_id(permission_id)
        if not success:
            return get_data_error_result(message="Permission not found")

        # Update permission
        updated = GroupKnowledgebasePermissionService.set_permission(
            group_id=permission.group_id,
            kb_id=permission.kb_id,
            can_read=req.get("can_read", permission.can_read),
            can_update=req.get("can_update", permission.can_update),
            can_delete=req.get("can_delete", permission.can_delete),
            can_create=req.get("can_create", permission.can_create)
        )

        return get_json_result(data={
            "id": updated.id,
            "group_id": updated.group_id,
            "kb_id": updated.kb_id,
            "can_read": updated.can_read,
            "can_update": updated.can_update,
            "can_delete": updated.can_delete,
            "can_create": updated.can_create
        })
    except Exception as e:
        return server_error_response(e)


@manager.route('/permission/kb/<permission_id>', methods=['DELETE'])  # noqa: F821
@login_required
@require_admin()
async def delete_kb_permission(permission_id):
    """
    Delete a knowledge base permission.

    Path parameters:
        - permission_id: ID of the permission to delete
    """
    try:
        success, permission = GroupKnowledgebasePermissionService.get_by_id(permission_id)
        if not success:
            return get_data_error_result(message="Permission not found")

        GroupKnowledgebasePermissionService.remove_permission(permission_id)
        return get_json_result(data=True, message="Permission deleted successfully")
    except Exception as e:
        return server_error_response(e)


@manager.route('/permission/kb/<kb_id>/list', methods=['GET'])  # noqa: F821
@login_required
async def get_kb_permissions(kb_id):
    """
    Get all permissions for a knowledge base.

    Path parameters:
        - kb_id: ID of the knowledge base

    Note: Only admin users can view permissions
    """
    try:
        if not is_admin(current_user.id):
            return get_json_result(
                code=RetCode.FORBIDDEN,
                message="Admin access required"
            )

        # Verify KB exists
        success, kb = KnowledgebaseService.get_by_id(kb_id)
        if not success:
            return get_data_error_result(message="Knowledge base not found")

        permissions = GroupKnowledgebasePermissionService.get_kb_permissions(kb_id)
        return get_json_result(data=permissions)
    except Exception as e:
        return server_error_response(e)


@manager.route('/permission/my', methods=['GET'])  # noqa: F821
@login_required
async def get_my_permissions():
    """
    Get all permissions for the current user.

    Returns:
        - user_id: Current user's ID
        - is_admin: Whether user is admin
        - groups: List of groups user belongs to
        - kb_permissions: Permissions per knowledge base
    """
    try:
        permissions = PermissionService.get_user_all_permissions(current_user.id)
        return get_json_result(data=permissions)
    except Exception as e:
        return server_error_response(e)


# ============================================================================
# Admin User Management Endpoints
# ============================================================================

@manager.route('/admin/users', methods=['GET'])  # noqa: F821
@login_required
@require_admin()
async def list_all_users():
    """
    List all users in the system.

    Query parameters:
        - page (int): Page number (default: 1)
        - page_size (int): Items per page (default: 20)
        - search (str): Search term for email/nickname

    Note: Admin only endpoint
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        search_term = request.args.get('search', '')

        users = UserService.query(status=StatusEnum.VALID.value)

        # Filter by search term if provided
        if search_term:
            users = [u for u in users if search_term.lower() in u.email.lower()
                     or search_term.lower() in (u.nickname or '').lower()]

        # Pagination
        total = len(users)
        start = (page - 1) * page_size
        end = start + page_size
        users_page = users[start:end]

        result = []
        for user in users_page:
            user_groups = UserGroupMemberService.get_user_groups(user.id)
            result.append({
                "id": user.id,
                "email": user.email,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "is_admin": any(g.is_admin for g in user_groups),
                "groups": [{"id": g.id, "name": g.name} for g in user_groups],
                "create_time": user.create_time,
                "last_login_time": user.last_login_time
            })

        return get_json_result(data={
            "users": result,
            "total": total,
            "page": page,
            "page_size": page_size
        })
    except Exception as e:
        return server_error_response(e)


@manager.route('/admin/user/<user_id>', methods=['DELETE'])  # noqa: F821
@login_required
@require_admin()
async def delete_user(user_id):
    """
    Delete a user from the system.

    Path parameters:
        - user_id: ID of the user to delete

    Note: Cannot delete yourself or other admin users
    """
    try:
        # Cannot delete yourself
        if user_id == current_user.id:
            return get_json_result(
                code=RetCode.FORBIDDEN,
                message="Cannot delete yourself"
            )

        # Check if user exists
        user = UserService.filter_by_id(user_id)
        if not user:
            return get_data_error_result(message="User not found")

        # Cannot delete other admin users
        if UserGroupMemberService.is_user_admin(user_id):
            return get_json_result(
                code=RetCode.FORBIDDEN,
                message="Cannot delete admin users"
            )

        # Soft delete user
        UserService.update_by_id(user_id, {"status": StatusEnum.INVALID.value})

        return get_json_result(data=True, message="User deleted successfully")
    except Exception as e:
        return server_error_response(e)
