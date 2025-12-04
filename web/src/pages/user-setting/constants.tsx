import {
  ApiIcon,
  LogOutIcon,
  ModelProviderIcon,
  PasswordIcon,
  ProfileIcon,
} from '@/assets/icon/next-icon';
import { LLMFactory } from '@/constants/llm';
import { UserSettingRouteKey } from '@/constants/setting';
import { MonitorOutlined } from '@ant-design/icons';

export const UserSettingIconMap = {
  [UserSettingRouteKey.Profile]: <ProfileIcon />,
  [UserSettingRouteKey.Password]: <PasswordIcon />,
  [UserSettingRouteKey.Model]: <ModelProviderIcon />,
  [UserSettingRouteKey.System]: <MonitorOutlined style={{ fontSize: 24 }} />,
  [UserSettingRouteKey.Logout]: <LogOutIcon />,
  [UserSettingRouteKey.Api]: <ApiIcon />,
};

export * from '@/constants/setting';

export const LocalLlmFactories = [
  LLMFactory.OpenRouter,
  LLMFactory.HuggingFace,
];

export enum TenantRole {
  Owner = 'owner',
  Invite = 'invite',
  Normal = 'normal',
}
