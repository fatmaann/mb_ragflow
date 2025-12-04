import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { getMyPermissionsApi, MyPermission } from '@/services/rbac-service';

export interface KbPermissions {
  canRead: boolean;
  canCreate: boolean;
  canUpdate: boolean;
  canDelete: boolean;
}

export const useMyPermissions = () => {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['rbac/myPermissions'],
    queryFn: async () => {
      const res = await getMyPermissionsApi();
      return (res?.data?.data || []) as MyPermission[];
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false,
  });

  return {
    permissions: data || [],
    isLoading,
    error,
    refetch,
  };
};

export const useKbPermission = (kbId: string): KbPermissions => {
  const { permissions, isLoading } = useMyPermissions();

  const kbPermission = useMemo(() => {
    if (isLoading || !kbId) {
      return {
        canRead: false,
        canCreate: false,
        canUpdate: false,
        canDelete: false,
      };
    }

    const perm = permissions.find((p) => p.kb_id === kbId);
    if (!perm) {
      // No explicit permission found - default to no access
      return {
        canRead: false,
        canCreate: false,
        canUpdate: false,
        canDelete: false,
      };
    }

    return {
      canRead: perm.can_read,
      canCreate: perm.can_create,
      canUpdate: perm.can_update,
      canDelete: perm.can_delete,
    };
  }, [permissions, kbId, isLoading]);

  return kbPermission;
};

export const useCanAccessKb = (kbId: string): boolean => {
  const { canRead } = useKbPermission(kbId);
  return canRead;
};

export const useCanModifyKb = (kbId: string): boolean => {
  const { canUpdate, canDelete } = useKbPermission(kbId);
  return canUpdate || canDelete;
};

export const useCanCreateInKb = (kbId: string): boolean => {
  const { canCreate } = useKbPermission(kbId);
  return canCreate;
};

// Check if user can access all KBs in a list (for chat assistants)
export const useCanAccessAllKbs = (kbIds: string[]): boolean => {
  const { permissions, isLoading } = useMyPermissions();

  return useMemo(() => {
    if (isLoading || !kbIds || kbIds.length === 0) {
      return false;
    }

    return kbIds.every((kbId) => {
      const perm = permissions.find((p) => p.kb_id === kbId);
      return perm?.can_read ?? false;
    });
  }, [permissions, kbIds, isLoading]);
};

export default useMyPermissions;
