import { IS_ENTERPRISE } from './pages/admin/utils';

export enum Routes {
  Root = '/',
  Login = '/login-next',
  Logout = '/logout',
  Home = '/home',
  Datasets = '/datasets',
  DatasetBase = '/dataset',
  Dataset = `${Routes.DatasetBase}${Routes.DatasetBase}`,
  Chats = '/next-chats',
  Chat = '/next-chat',
  ProfileSetting = '/profile-setting',
  Profile = '/profile',
  Api = '/api',
  Model = '/model',
  DatasetTesting = '/testing',
  Chunk = '/chunk',
  ChunkResult = `${Chunk}${Chunk}`,
  Parsed = '/parsed',
  ParsedResult = `${Chunk}${Parsed}`,
  Result = '/result',
  ResultView = `${Chunk}${Result}`,
  KnowledgeGraph = '/knowledge-graph',
  ChatShare = `${Chats}/share`,
  ChatWidget = `${Chats}/widget`,
  UserSetting = '/user-setting',
  DataSetOverview = '/dataset-overview',
  DataSetSetting = '/dataset-setting',
  Admin = '/admin',
  AdminServices = `${Admin}/services`,
  AdminUserManagement = `${Admin}/users`,
  AdminWhitelist = `${Admin}/whitelist`,
  AdminRoles = `${Admin}/roles`,
  AdminMonitoring = `${Admin}/monitoring`,
  AdminGroups = `${Admin}/groups`,
  AdminPermissions = `${Admin}/permissions`,
}

const routes = [
  {
    path: '/login',
    component: '@/pages/login-next',
    layout: false,
  },
  {
    path: '/login-next',
    component: '@/pages/login-next',
    layout: false,
  },
  {
    path: Routes.ChatShare,
    component: `@/pages${Routes.ChatShare}`,
    layout: false,
  },
  {
    path: Routes.ChatWidget,
    component: `@/pages${Routes.ChatWidget}`,
    layout: false,
  },
  {
    path: '/document/:id',
    component: '@/pages/document-viewer',
    layout: false,
  },
  {
    path: '/*',
    component: '@/pages/404',
    layout: false,
  },
  {
    path: Routes.Root,
    layout: false,
    component: '@/layouts/next',
    wrappers: ['@/wrappers/auth'],
    routes: [
      {
        path: Routes.Root,
        component: `@/pages${Routes.Home}`,
      },
    ],
  },
  {
    path: Routes.Datasets,
    layout: false,
    component: '@/layouts/next',
    routes: [
      {
        path: Routes.Datasets,
        component: `@/pages${Routes.Datasets}`,
      },
    ],
  },
  {
    path: Routes.Chats,
    layout: false,
    component: '@/layouts/next',
    routes: [
      {
        path: Routes.Chats,
        component: `@/pages${Routes.Chats}`,
      },
    ],
  },
  {
    path: Routes.Chat + '/:id',
    layout: false,
    component: `@/pages${Routes.Chats}/chat`,
  },
  {
    path: Routes.DatasetBase,
    layout: false,
    component: '@/layouts/next',
    routes: [{ path: Routes.DatasetBase, redirect: Routes.Dataset }],
  },
  {
    path: Routes.DatasetBase,
    layout: false,
    component: `@/pages${Routes.DatasetBase}`,
    routes: [
      {
        path: `${Routes.Dataset}/:id`,
        component: `@/pages${Routes.Dataset}`,
      },
      {
        path: `${Routes.DatasetBase}${Routes.DatasetTesting}/:id`,
        component: `@/pages${Routes.DatasetBase}${Routes.DatasetTesting}`,
      },
      {
        path: `${Routes.DatasetBase}${Routes.KnowledgeGraph}/:id`,
        component: `@/pages${Routes.DatasetBase}${Routes.KnowledgeGraph}`,
      },
      {
        path: `${Routes.DatasetBase}${Routes.DataSetOverview}/:id`,
        component: `@/pages${Routes.DatasetBase}${Routes.DataSetOverview}`,
      },
      {
        path: `${Routes.DatasetBase}${Routes.DataSetSetting}/:id`,
        component: `@/pages${Routes.DatasetBase}${Routes.DataSetSetting}`,
      },
    ],
  },
  {
    path: `${Routes.ParsedResult}/chunks`,
    layout: false,
    component: `@/pages${Routes.Chunk}/parsed-result/add-knowledge/components/knowledge-chunk`,
  },
  {
    path: Routes.Chunk,
    layout: false,
    routes: [
      {
        path: Routes.Chunk,
        component: `@/pages${Routes.Chunk}`,
        routes: [
          {
            path: `${Routes.ChunkResult}/:id`,
            component: `@/pages${Routes.Chunk}/chunk-result`,
          },
          {
            path: `${Routes.ResultView}/:id`,
            component: `@/pages${Routes.Chunk}/result-view`,
          },
        ],
      },
    ],
  },
  {
    path: Routes.Chunk,
    layout: false,
    component: `@/pages${Routes.Chunk}`,
  },
  {
    path: '/user-setting',
    component: '@/pages/user-setting',
    layout: false,
    routes: [
      { path: '/user-setting', redirect: '/user-setting/profile' },
      {
        path: '/user-setting/profile',
        component: '@/pages/user-setting/profile',
      },
      {
        path: '/user-setting/locale',
        component: '@/pages/user-setting/setting-locale',
      },
      {
        path: '/user-setting/model',
        component: '@/pages/user-setting/setting-model',
      },
      {
        path: `/user-setting${Routes.Api}`,
        component: '@/pages/user-setting/setting-api',
      },
    ],
  },

  // Admin routes
  {
    path: Routes.Admin,
    layout: false,
    component: `@/pages/admin/layouts/root-layout`,
    routes: [
      {
        path: '',
        component: `@/pages/admin/login`,
      },
      {
        path: `${Routes.AdminUserManagement}/:id`,
        wrappers: ['@/pages/admin/wrappers/authorized'],
        component: `@/pages/admin/user-detail`,
      },
      {
        path: Routes.Admin,
        component: `@/pages/admin/layouts/navigation-layout`,
        wrappers: ['@/pages/admin/wrappers/authorized'],
        routes: [
          {
            path: Routes.AdminServices,
            component: `@/pages/admin/service-status`,
          },
          {
            path: Routes.AdminUserManagement,
            component: `@/pages/admin/users`,
          },
          {
            path: Routes.AdminGroups,
            component: `@/pages/admin/groups`,
          },
          {
            path: Routes.AdminPermissions,
            component: `@/pages/admin/permissions`,
          },

          ...(IS_ENTERPRISE
            ? [
                {
                  path: Routes.AdminWhitelist,
                  component: `@/pages/admin/whitelist`,
                },
                {
                  path: Routes.AdminRoles,
                  component: `@/pages/admin/roles`,
                },
                {
                  path: Routes.AdminMonitoring,
                  component: `@/pages/admin/monitoring`,
                },
              ]
            : []),
        ],
      },
    ],
  },
];

export default routes;
