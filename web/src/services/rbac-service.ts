import api from '@/utils/api';
import registerServer from '@/utils/register-server';
import request from '@/utils/request';

const {
  listGroups,
  createGroup,
  updateGroup,
  deleteGroup,
  listGroupMembers,
  addGroupMember,
  removeGroupMember,
  setKbPermission,
  updateKbPermission,
  deleteKbPermission,
  getKbPermissions,
  getMyPermissions,
} = api;

// Types
export interface UserGroup {
  id: string;
  name: string;
  description: string | null;
  is_admin: boolean;
  create_time: string;
  update_time: string;
}

export interface GroupMember {
  id: string;
  user_id: string;
  group_id: string;
  email: string;
  nickname: string;
  create_time: string;
}

export interface KbPermission {
  id: string;
  group_id: string;
  group_name: string;
  kb_id: string;
  kb_name: string;
  can_read: boolean;
  can_update: boolean;
  can_delete: boolean;
  can_create: boolean;
  create_time: string;
  update_time: string;
}

export interface MyPermission {
  kb_id: string;
  kb_name: string;
  can_read: boolean;
  can_update: boolean;
  can_delete: boolean;
  can_create: boolean;
}

// Group Management
export const listGroupsApi = () => {
  return request.get(listGroups);
};

export const createGroupApi = (data: {
  name: string;
  description?: string;
  is_admin?: boolean;
}) => {
  return request.post(createGroup, data);
};

export const updateGroupApi = (
  groupId: string,
  data: { name?: string; description?: string; is_admin?: boolean },
) => {
  return request.put(updateGroup(groupId), data);
};

export const deleteGroupApi = (groupId: string) => {
  return request.delete(deleteGroup(groupId));
};

// Group Membership
export const listGroupMembersApi = (groupId: string) => {
  return request.get(listGroupMembers(groupId));
};

export const addGroupMemberApi = (groupId: string, userId: string) => {
  return request.post(addGroupMember(groupId), { user_id: userId });
};

export const removeGroupMemberApi = (groupId: string, userId: string) => {
  return request.delete(removeGroupMember(groupId, userId));
};

// Knowledge Base Permissions
export const setKbPermissionApi = (data: {
  group_id: string;
  kb_id: string;
  can_read?: boolean;
  can_update?: boolean;
  can_delete?: boolean;
  can_create?: boolean;
}) => {
  return request.post(setKbPermission, data);
};

export const updateKbPermissionApi = (
  permissionId: string,
  data: {
    can_read?: boolean;
    can_update?: boolean;
    can_delete?: boolean;
    can_create?: boolean;
  },
) => {
  return request.put(updateKbPermission(permissionId), data);
};

export const deleteKbPermissionApi = (permissionId: string) => {
  return request.delete(deleteKbPermission(permissionId));
};

export const getKbPermissionsApi = (kbId: string) => {
  return request.get(getKbPermissions(kbId));
};

export const getMyPermissionsApi = () => {
  return request.get(getMyPermissions);
};

// Register server methods for hooks
const methods = {
  listGroups: listGroupsApi,
  createGroup: createGroupApi,
  updateGroup: updateGroupApi,
  deleteGroup: deleteGroupApi,
  listGroupMembers: listGroupMembersApi,
  addGroupMember: addGroupMemberApi,
  removeGroupMember: removeGroupMemberApi,
  setKbPermission: setKbPermissionApi,
  updateKbPermission: updateKbPermissionApi,
  deleteKbPermission: deleteKbPermissionApi,
  getKbPermissions: getKbPermissionsApi,
  getMyPermissions: getMyPermissionsApi,
};

registerServer<keyof typeof methods>(methods);

export default methods;
