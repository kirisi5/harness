# Hopewind Project Web 实习成果总结报告

## 一、项目背景与目标概述

Hopewind Project Web 是公司内部用于项目管理、任务协同、预算配置、交付件管理、流程审批和系统通知的前端平台。项目以 Vue 3、TypeScript、Pinia、Vue Router、Element Plus、Axios 和 vue-i18n 为基础，围绕“项目主流程 + 业务子模块 + 公共能力”构建统一前端体系。

本次实习围绕 `v1.2.2` 和 `v1.3.1` 两个版本展开，核心目标是：

1. 完成既有业务模块的功能补齐与稳定性优化；
2. 打通版本管理、路由恢复、升级公告等平台级能力；
3. 在项目计划、预算版本、交付件版本等场景中实现更清晰的版本控制逻辑；
4. 通过接口联调、页面重构和状态联动，提升系统可维护性与用户体验。

---

## 二、实习期间负责的具体模块与任务

结合两个版本的开发内容，我主要参与了以下模块：

### 1. 请求基础设施与环境配置
- 统一请求地址、超时时间和版本信息注入逻辑；
- 保障本地开发环境与部署环境共用同一套请求封装；
- 支持前端请求携带应用版本号，便于后端识别发布版本。

### 2. 路由与应用稳定性
- 参与动态路由加载与菜单恢复逻辑；
- 处理版本更新后路由加载失败的问题；
- 优化任务详情页返回路径记录，保证用户返回时回到正确上下文。

### 3. 升级公告与消息提醒
- 接入升级公告弹窗；
- 在登录和定时轮询场景下拉取公告与未读消息；
- 在用户确认后完成公告已读状态回写。

### 4. 项目计划版本模块
- 完成项目计划版本列表展示；
- 支持当前版本选择、版本状态展示和版本相关操作；
- 对版本对比入口做页面承接与交互预留。

### 5. 预算版本配置模块
- 完成预算版本分页查询、筛选和编辑；
- 支持版本初始化规划；
- 处理业务大类、版本类型、统计标识等字段联动。

### 6. 项目计划主操作区
- 维护项目计划版本切换后的操作按钮状态；
- 支持任务裁剪、任务分解、资源冲突检测、一键匹配团队成员等操作；
- 保障未保存内容和空任务场景下的交互提示正确。

---

## 三、1.2.2 版本代码的核心功能实现

`v1.2.2` 阶段的重点是把“基础请求能力、项目版本列表、预算版本配置、页面稳定性”先做扎实。这一阶段的代码特点是：逻辑清晰、依赖少、重点放在基础业务闭环和页面可用性上。

### 3.1 请求配置：统一环境地址与超时策略

#### 代码逻辑说明

项目请求层通过当前浏览器地址判断服务端 API 根路径：本地开发时直连开发环境，部署后拼接当前站点的 `/api/`。同时将超时时间统一设置为 5 分钟，适应流程保存、复杂查询和文件类操作。

#### 关键代码片段

```ts
// src/config/request.ts
const { hostname, origin } = window.location;

export const requestConfig = {
  // 本地开发环境固定走开发服务，部署后走当前站点的 API 前缀。
  serverUrl: ['127.0.0.1', 'localhost'].includes(hostname)
    ? 'http://devpm.hopewind.com/api/'
    : `${origin}/api/`,
  // 复杂业务场景请求耗时较长，统一放宽超时限制。
  requestTimeout: 1000 * 60 * 5, // 超时时间调整为5分钟
};

/**
 * @description 获取域名
 */
export const getHostname = () => {
  const regex = /\/\/(.*?)\/api/;
  const match = requestConfig.serverUrl.match(regex);
  if (match && match.length > 1) {
    return match[1];
  }
  return '';
};
```

#### 实现要点
- 通过 `hostname` 区分本地与线上环境；
- 避免每个接口模块手动维护地址；
- 为后续请求版本控制、环境切换和域名提取提供统一入口。

---

### 3.2 项目计划版本列表：版本展示与选择

#### 代码逻辑说明

项目计划版本列表页通过 `HwPage` 统一承载表格、分页和操作按钮。页面加载时根据 `projectId` 拉取版本数据，选中项目变化后自动刷新。版本类型使用 `isBaselineVersion` 判断是否为基线版本，操作列支持查看流程与查看详情。

#### 关键代码片段

```vue
<!-- src/views/project/project-plan/components/ProjectPlanVersion.vue -->
<template>
  <hw-page ref="tableRef" :info="pageInfo" @selection-change="selectVersionList" />
</template>

<script lang="ts" setup>
  import { ref, reactive, watch, onMounted } from 'vue';
  import { HwPage, usePage, paginationInfo } from '@hopecloud-web/components';
  import type { TableInfo } from '@hopecloud-web/components/base-table/type';
  import type { PageInfoInterface, OperationHeaderButton } from '@/components/base-page/type';
  import { useI18n } from 'vue-i18n';
  import { cloneDeep } from 'lodash';
  import { ElMessage } from 'element-plus';
  import { projectPlanVersionApiMap } from '@/api/project/plan';
  import { useProjectStore } from '@/stores';
  import { storeToRefs } from 'pinia';
  import { ProjectVersion } from '../types';
  import { useRoute } from 'vue-router';
  import { getUserInfoApi } from '@/api/common/userInfo';

  const emits = defineEmits(['view-selected-version-project']);
  const { t } = useI18n();
  const route = useRoute();
  const { selectedProject } = storeToRefs(useProjectStore());
  const tableRef = ref<typeof HwPage>();
  const query = ref({});
  const selectionList = ref<Record<string, unknown>[]>([]);

  const tt = (key: string) => t(`hopewind.web.project.plan.${key}`);

  const tableInfo: TableInfo = reactive({
    columns: [
      {
        prop: 'versionType',
        label: tt('versionType'),
        formatValue: (row: ProjectVersion) => {
          return row.isBaselineVersion ? tt('baseLine') : tt('nonBaseLine');
        },
      },
      { prop: 'planVersion', label: tt('versionCode') },
      { prop: 'updatedTime', label: tt('updateTime') },
      {
        prop: 'updateByName',
        label: t('hopewind.web.common.operator'),
        slotName: 'AVATAR',
        avatarImg: 'updateByImgUrl',
        fetchMethod: getUserInfoApi,
        userIdField: 'updatedById',
      },
      {
        label: t('hopewind.web.baseTable.index.operate'),
        prop: 'operationColumn',
        actions: [
          {
            customSvg: 'project-plan-query-process',
            text: tt('queryProcess'),
            handler: (row: Record<string, unknown>) => {
              const { processInstanceId } = row;
              const processFormUrl = `/#/developer/process-manage/process-form/index?processInstanceId=${processInstanceId}`;
              window.open(processFormUrl, '_blank');
            },
            code: 'WHITE_BUTTON',
            isShow: (row: ProjectVersion) => !!row.processInstanceId,
          },
          {
            icon: 'View',
            text: t('hopewind.web.common.detail'),
            handler: (row: ProjectVersion) => {
              emits('view-selected-version-project', row);
            },
            code: 'WHITE_BUTTON',
          },
        ],
        slotName: 'ACTION',
        fixed: 'right',
      },
    ],
    showIndexColumn: false,
    tableData: [],
    rowKey: 'id',
    showSelectColumn: true,
    tableName: 'ProjectPlanVersionTable',
  });

  const operationHeaderButton: OperationHeaderButton[] = [
    {
      text: tt('versionComparison'),
      code: 'SystemOperateLogConfig',
      selectedRequired: true,
      handler: () => {
        ElMessage.warning('版本对比待开发...');
      },
    },
  ];

  const pageInfo = reactive<PageInfoInterface>({
    operationHeaderButton,
    tableInfo,
    paginationInfo: cloneDeep(paginationInfo),
  });

  const { loadInfo } = usePage(
    pageInfo,
    query.value,
    projectPlanVersionApiMap.projectPlanVersionListApi
  );

  const loadTableInfo = () => {
    loadInfo({
      projectId: route.query.projectId as string,
    });
    tableRef.value.clearSelection();
  };

  const selectVersionList = (list: Record<string, unknown>[]) => {
    selectionList.value = list;
  };

  onMounted(() => {
    loadTableInfo();
  });

  watch(
    () => selectedProject.value,
    () => {
      loadTableInfo();
    }
  );
</script>
```

#### 关键算法与逻辑
- 以 `projectId` 作为版本列表查询主键；
- 通过 `watch(selectedProject)` 自动刷新列表，保证切换项目后数据同步；
- 用 `formatValue` 实现基线版本与普通版本的显示转换；
- 通过 `selectionList` 保留当前选中行，支持后续版本操作扩展。

#### 实现价值
这一模块完成了项目计划版本的基础承载，是后续版本切换、流程查看和版本对比的入口。

---

### 3.3 预算版本配置：筛选、编辑与初始化

#### 代码逻辑说明

预算版本配置页采用“高级查询 + 表格 + 弹窗”的组合方式。页面支持业务大类、版本类型、版本号/名称等多维筛选，表格中可直接编辑版本配置，并提供“启动规划”入口。

#### 关键代码片段

```vue
<!-- src/views/budget/budget-allocation/version-config/index.vue -->
<template>
  <div class="version-config">
    <hw-page
      ref="tableRef"
      :info="pageInfo"
      @load-info="loadInfo"
      @reset-search="loadData"
      @column-switch-change="handleActive"
    />

    <edit-dialog ref="editDialogRef" @reload="resetSearch" />
    <initial-dialog ref="initialDialogRef" @reload="resetSearch" />
  </div>
</template>

<script lang="ts" setup>
  import { ref, reactive, nextTick } from 'vue';
  import { cloneDeep } from 'lodash';
  import { useI18n } from 'vue-i18n';
  import { HwPage, usePage, paginationInfo } from '@hopecloud-web/components';
  import { AdvancedQueryInfo } from '@hopecloud-web/components/advanced-query/types';
  import { useAdvancedQuery } from '@/hooks/common/useAdvancedQuery';
  import { AdvancedQueryFormType, AdvancedQueryFieldType } from '@/enums/common/advancedQueryEnum';
  import { Any } from '@/utils/types';
  import { getVersionConfigPageApi } from '@/api/budget/budget-config/versionConfig';
  import { getBusinessCategoryTreeApi } from '@/api/system/basic-config/businessConfig';
  import EditDialog from './components/EditDialog.vue';
  import InitialDialog from './components/InitialDialog.vue';
  import { useFormCache } from '@/hooks/common/useFormCache';
  import { FORM_CACHE_KEY } from '@/enums/common/formCacheKeys';

  const { t } = useI18n();
  const tt = (i18n: string) => t(`hopewind.web.budget.versionConfig.${i18n}`);

  const VerTypeEnum = [
    { label: tt('temporary'), value: 0 },
    { label: tt('benchmark'), value: 1 },
    { label: tt('rolling'), value: 2 },
  ];

  const query = ref({});
  const tableRef = ref();
  const businessCategoryEnum = ref<{ label: string; value: number }[]>([]);
  const editDialogRef = ref<InstanceType<typeof EditDialog>>();
  const initialDialogRef = ref<InstanceType<typeof InitialDialog>>();
  const { matchAdvancedQueryFormItemConfig } = useAdvancedQuery();
  const { loadCache, saveCache } = useFormCache(FORM_CACHE_KEY.BUDGET_ALLOCATION_VERSION_CONFIG);

  const tableInfo = reactive({
    columns: [
      { prop: 'businessCategoryName', label: tt('businessTypeName') },
      { prop: 'verName', label: tt('verName') },
      { prop: 'verCode', label: tt('verCode') },
      { prop: 'verTypeName', label: tt('verTypeName') },
      { prop: 'budgetDate', label: tt('budgetDate') },
      { prop: 'updatedTime', label: tt('updatedTime') },
      {
        prop: 'statisticMark',
        label: tt('statisticMark'),
        slotName: 'SWITCH',
        code: 'SystemBusinessConfigActive',
      },
      { prop: 'costPerDay', label: tt('costPerDay') },
      {
        prop: 'operationColumn',
        label: t('hopewind.web.common.action'),
        width: 120,
        actions: [
          {
            icon: 'EditPen',
            text: t('hopewind.web.common.edit'),
            handler: (row: Any) => {
              editDialogRef.value?.openDialog({ ...row });
            },
            isShow: (row: Any) => row.verType,
            code: 'BudgetVersionConfigEdit',
          },
        ],
        slotName: 'ACTION',
      },
    ],
    tableData: [],
    showIndexColumn: true,
    rowKey: 'id',
  });

  const advancedQueryInfo: AdvancedQueryInfo = {
    leftBasicSearchForm: [
      {
        key: 'businessCategory',
        formType: 'select',
        placeholder: tt('businessCategoryName'),
        options: businessCategoryEnum,
      },
      {
        key: 'verType',
        formType: 'select',
        placeholder: tt('verTypeName'),
        options: VerTypeEnum,
      },
    ],
    rightBasicSearchForm: [
      {
        key: 'verCodeAndName',
        formType: 'input',
        placeholder: tt('verCodeOrName'),
      },
    ],
    advancedConditionItems: [
      matchAdvancedQueryFormItemConfig({
        formType: AdvancedQueryFormType.TEXT_INPUT,
        field: 'bv.ver_code',
        fieldName: tt('verCode'),
        fieldType: AdvancedQueryFieldType.TEXT,
      }),
      matchAdvancedQueryFormItemConfig({
        formType: AdvancedQueryFormType.DATE_PICKER,
        field: 'bv.updated_time',
        fieldName: tt('updatedTime'),
        fieldType: AdvancedQueryFieldType.DATE,
      }),
      matchAdvancedQueryFormItemConfig({
        formType: AdvancedQueryFormType.CHECK_BOX,
        field: 'bv.statistic_mark',
        fieldName: tt('statisticMark'),
        fieldType: AdvancedQueryFieldType.DICT_VALUE,
        options: [
          { value: 0, label: tt('no') },
          { value: 1, label: tt('yes') },
        ],
      }),
      matchAdvancedQueryFormItemConfig({
        formType: AdvancedQueryFormType.NUMBER_INPUT,
        field: 'mhc.cost_per_day',
        fieldName: tt('costPerDay'),
        fieldType: AdvancedQueryFieldType.NUMBER,
      }),
    ],
  };

  const operationHeaderButton = [
    {
      text: tt('initiatePlan'),
      businessType: 'firstly',
      handler: () => {
        initialDialogRef.value?.openDialog();
      },
      code: 'BudgetVersionConfigInitial',
    },
  ];

  const pageInfo = reactive({
    advancedQueryInfo,
    tableInfo,
    operationHeaderButton,
    paginationInfo: cloneDeep(paginationInfo),
  });

  const { loadInfo: loadPageInfo, resetSearch } = usePage(pageInfo, query, getVersionConfigPageApi);

  const loadInfo = (params?: any) => {
    if (!params) {
      const cacheData = loadCache();
      if (cacheData && Object.entries(cacheData).length) {
        return loadPageInfo(cacheData);
      }
    }
    return loadPageInfo(params);
  };

  const loadData = (args: any) => {
    saveCache(args);
    resetSearch(args);
  };

  const getBusinessEnum = async () => {
    const { result }: Any = await getBusinessCategoryTreeApi();
    businessCategoryEnum.value = result.map((item: Any) => ({
      label: item.categoryName,
      value: Number(item.id),
    }));
  };
</script>
```

#### 关键逻辑说明
- 使用高级查询配置抽象筛选字段，减少重复表单代码；
- 用缓存保存查询条件，刷新后可回填上次筛选结果；
- 通过 `getBusinessCategoryTreeApi` 动态填充业务大类下拉；
- 编辑与初始化动作拆分到独立弹窗，便于复用和维护。

#### 实现价值
该模块在 `v1.2.2` 阶段完成了预算版本管理的核心列表能力，为后续版本类型扩展和业务统计提供了基础。

---

### 3.4 项目计划主操作区：版本切换与任务操作联动

#### 代码逻辑说明

项目计划页面的操作区会根据当前版本、权限、是否处于滚动计划等状态动态控制按钮可用性。页面还会校验是否存在未保存内容、是否有可操作任务，避免误操作。

#### 关键代码片段

```vue
<!-- src/views/project/project-plan/components/SelectVersion.vue -->
<script lang="ts" setup>
  import { ref, onUnmounted, computed, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import AdaptiveButtonGroup from './AdaptiveButtonGroup.vue';
  import { useFormDialog } from '@hopecloud-web/components';
  import ResourceConflictDetection from './ResourceConflictDetection.vue';
  import TaskTrimming from './TaskTrimming.vue';
  import TaskDecomposition from './TaskDecomposition.vue';
  import ProjectPlanInfo from './ProjectPlanInfo.vue';
  import TaskScheduleAdjuster from './TaskScheduleAdjuster.vue';
  import { ElMessage } from 'element-plus';
  import { CONSTANT_NUMBER } from '@/constant';
  import { projectPlanVersionApiMap } from '@/api/project/plan';
  import { ProjectVersion } from '../types';
  import { useProjectStore } from '@/stores';
  import { useLayoutStoreHook } from '@/stores';
  import { storeToRefs } from 'pinia';
  import { usePlusProjectColumn } from '@/views/project/usePlusProjectColumn';
  import { projectPlanningApiMap } from '../../../../api/project/plan';
  import { useRoute } from 'vue-router';
  import { addPrefix } from '@/utils/common/utils';
  import bus from '@/utils/common/bus';
  import { debounce } from 'lodash';

  const emits = defineEmits([
    'select-version',
    'match-team-member',
    'confirm-plan',
    'task-decomposition',
    'crop-task',
    'refresh-plan-status',
    'refresh-after-adjust-task-schedule',
  ]);

  const { t } = useI18n();
  const { showFormModal } = useFormDialog();
  const route = useRoute();
  const resourceConflictDetectionRef = ref<typeof ResourceConflictDetection>();
  const taskTrimmingRef = ref<typeof TaskTrimming>();
  const taskDecompositionRef = ref<typeof TaskDecomposition>();
  const selectedVersion = ref('');
  const {
    currentProjectVersion,
    projectInstance,
    actionButtonGroupPermission,
    rollVisible,
    hasUnsavedContent,
  } = storeToRefs(useProjectStore());
  const { collectPropertyEmptyTasks } = usePlusProjectColumn();
  const { isCollapse } = storeToRefs(useLayoutStoreHook());
  const projectVersionList = ref<ProjectVersion[]>([]);
  const adaptiveButtonGroupRef = ref<typeof AdaptiveButtonGroup>();
  const refreshKey = ref(CONSTANT_NUMBER.CONSTANT_0);

  const tt = (key: string) => t(`hopewind.web.project.plan.${key}`);

  const setButtonDisabled = (permissionCode: string) => {
    const button = actionButtonGroupPermission.value?.find(
      (item) => item.permissionCode === permissionCode
    );
    if (permissionCode === 'PMProjectPlanRolling') {
      return !button?.enabled;
    }
    if (permissionCode === 'PMProjectResourceCheck' && rollVisible.value) {
      return false;
    }
    return !button?.enabled || rollVisible.value;
  };

  const validateTaskAndUnsaved = () => {
    const data = projectInstance.value?.getData();
    const tasks = data?.Tasks || [];
    if (hasUnsavedContent.value) {
      ElMessage.warning(tt('unsavedContentBeforeOption'));
    } else if (!tasks?.length) {
      ElMessage.warning(tt('noTaskForOption'));
    }
    return hasUnsavedContent.value || !tasks?.length;
  };

  const buttonList = computed(() => [
    {
      label: tt('projectPlanInfo'),
      type: 'primary',
      onClick: () => {
        projectPlanInfoRef.value?.openDialog();
      },
      permissionCode: addPrefix('ProjectPlanInfo'),
      disabled: setButtonDisabled(addPrefix('ProjectPlanInfo')),
    },
    {
      label: tt('oneClickMatching'),
      type: 'primary',
      onClick: () => {
        if (validateTaskAndUnsaved()) {
          return;
        }
        showFormModal({
          title: t('hopewind.web.common.tips'),
          confirmText: tt('oneClickMatchingTips'),
          handleConfirm: async ({ close, loading }) => {
            try {
              const { id: planId } = currentProjectVersion.value;
              const { result } = await projectPlanningApiMap.matchProjectTeamMemberApi({
                planId,
                projectId: route.query.projectId as string,
              });
              close();
              emits('match-team-member', result);
              ElMessage.success(t('hopewind.web.project.plan.teamMemberMatchSuccessfully'));
            } catch {
              /* empty */
            } finally {
              loading.value = false;
            }
          },
        });
      },
      permissionCode: addPrefix('ProjectPlanMemberMatch'),
      disabled: setButtonDisabled(addPrefix('ProjectPlanMemberMatch')),
    },
    {
      label: tt('resourceConflictDetection'),
      type: 'primary',
      onClick: (button) => {
        button.loading = true;
        resourceConflictDetectionRef.value?.resourceConflictDetection(() => {
          button.loading = false;
        });
      },
      permissionCode: addPrefix('ProjectResourceCheck'),
      disabled: setButtonDisabled(addPrefix('ProjectResourceCheck')),
    },
    {
      label: tt('taskTrimming'),
      type: 'primary',
      onClick: () => {
        const selectedList = projectInstance.value?.getSelecteds();
        if (!selectedList.length) {
          ElMessage.warning(tt('pleaseSelectTask'));
          return;
        }

        const taskList = [];
        for (const i in selectedList) {
          taskList.push(selectedList[i]);
        }
        taskTrimmingRef.value?.handleTaskTrimming(taskList);
      },
      permissionCode: addPrefix('ProjectTaskCut'),
      disabled: setButtonDisabled(addPrefix('ProjectTaskCut')),
    },
    {
      label: tt('taskDecomposition'),
      type: 'primary',
      onClick: () => {
        taskDecompositionRef.value?.handleTaskDecomposition();
      },
      permissionCode: addPrefix('ProjectTaskDecomposition'),
      disabled: setButtonDisabled(addPrefix('ProjectTaskDecomposition')),
    },
  ]);
</script>
```

#### 关键算法与交互策略
- 使用权限码控制按钮启停；
- 在计划滚动状态下，对非必要操作按钮统一禁用；
- 先校验未保存内容与任务数量，再允许执行高风险操作；
- 通过弹窗确认减少误操作；
- 对任务裁剪、任务分解、资源冲突检测等操作保持单独组件职责。

#### 实现价值
这一部分让项目计划页面从“展示型列表”升级为“可操作的计划协同中心”。

---

## 四、1.3.1 版本代码的功能迭代与优化点

`v1.3.1` 在 `v1.2.2` 的基础上，重点从“基础可用”走向“平台稳定、版本联动、通知闭环和流程恢复”。这一阶段的代码改动更关注系统性体验，而不仅是单页功能。

### 4.1 应用版本上报与升级公告

#### 代码逻辑说明

前端在启动时读取 `version.json`，把应用版本写入请求链路；同时在主入口挂载升级公告组件，通过登录事件和定时轮询拉取公告信息。公告关闭时会回写已读状态，并刷新消息中心未读数。

#### 关键代码片段

```ts
// src/utils/request/http.ts 中的版本读取逻辑
let appVersion = '';

fetch(
  `${window.location.protocol}//${window.location.host}/version.json?params=${new Date().getTime()}`
)
  .then((response) => response.json())
  .then((data) => {
    appVersion = data.version;
  });
```

```vue
<!-- src/App.vue -->
<template>
  <el-config-provider :locale="zh_CN">
    <router-view />
    <watermark />
    <upgrade-announcement />
  </el-config-provider>
</template>
```

```vue
<!-- src/components/upgrade-announcement/index.vue -->
<script lang="ts" setup>
  import { ref, onMounted, onUnmounted } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useUserStoreHook } from '@/stores/components/user';
  import bus from '@/utils/common/bus.ts';
  import { useMessageCenterHook } from '@/stores';
  import { getNotifyDetailApi, interiorSetReadExternalApi } from '@/api/system/notify';
  import { TimerEnum } from '@/enums/common/constantEnum';

  const { t } = useI18n();

  const drawerVisible = ref(false);
  const unreadCountTimer = ref();
  const upgradeNotifyTimer = ref();
  const notifyInfo = ref({
    title: '',
    content: '',
    id: '',
    publishVersion: '',
  });

  const queryUpgradeNotifyInfo = async () => {
    try {
      if (!useUserStoreHook().token) {
        return;
      }
      const { result } = await getNotifyDetailApi();
      if (result) {
        drawerVisible.value = true;
        notifyInfo.value = result;
      }
    } catch {
      /* empty */
    }
  };

  const closeDialog = () => {
    if (useUserStoreHook().token) {
      interiorSetReadExternalApi({ messageType: 10, id: notifyInfo.value.id }).then(() => {
        useMessageCenterHook().getMessageNumber();
        drawerVisible.value = false;
      });
    }
  };

  onMounted(() => {
    queryUpgradeNotifyInfo();
    bus.$on('search-upgrade-notify', () => {
      queryUpgradeNotifyInfo();
    });

    if (useUserStoreHook().token) {
      unreadCountTimer.value = setInterval(() => {
        useMessageCenterHook().getMessageNumber();
      }, TimerEnum.TIMER_FIVE_MINUTE);

      upgradeNotifyTimer.value = setInterval(() => {
        queryUpgradeNotifyInfo();
      }, TimerEnum.TIMER_ONE_HOUR);
    }
  });

  onUnmounted(() => {
    clearInterval(unreadCountTimer.value);
    clearInterval(upgradeNotifyTimer.value);
    bus.$off('search-upgrade-notify');
  });
</script>
```

#### 迭代价值
- `v1.2.2` 更偏“业务页面能跑通”；
- `v1.3.1` 开始补齐“发布后版本可感知、公告可触达、页面可恢复”的平台能力；
- 通过公告与版本文件联动，提升了前端发布后的可维护性。

---

### 4.2 路由更新容错与详情返回优化

#### 代码逻辑说明

`v1.3.1` 中路由系统补充了两个关键优化：

1. 当版本更新导致动态路由模块加载失败时，自动刷新页面；
2. 当进入项目计划任务详情页时，记录来源路由，返回后回到正确页面上下文。

#### 关键代码片段

```ts
// src/router/index.ts
const updateProjectPlanTaskDetailBackRoute = (to: Any, from: Any) => {
  const routerStore = useRouterStoreHook();

  if (to.path === PROJECT_PLAN_TASK_DETAIL_PATH) {
    const shouldRecordBackRoute =
      from.path && !['/', '/login'].includes(from.path) && from.path !== to.path;

    if (shouldRecordBackRoute) {
      routerStore.setDetailBackRoute(from.fullPath);
    } else if (from.path !== to.path) {
      // 刷新或直接打开详情页时清空持久化旧来源；同一路径仅切换 query 时保留原来源
      routerStore.setDetailBackRoute('');
    }

    return;
  }

  if (from.path === PROJECT_PLAN_TASK_DETAIL_PATH) {
    routerStore.setDetailBackRoute('');
  }
};

router.onError((error) => {
  const pattern = /failed(?=.*imported module)/i;
  const match = pattern.test(error);
  if (match) {
    setTimeout(() => {
      window.location.reload();
    }, 1000);
  }
});
```

#### 改进点对比
- `v1.2.2` 主要解决页面可访问、数据可展示；
- `v1.3.1` 进一步解决“版本更新后页面资源失效”和“详情页返回丢上下文”问题；
- 这类修复不直接增加业务功能，但显著提升了系统稳定性与用户体验。

---

### 4.3 项目计划版本与操作区的联动增强

#### 代码逻辑说明

在 `v1.3.1` 相关页面中，项目计划版本的展示与主操作区联动更加紧密：版本状态、基线版本、新版本标识、权限按钮和滚动计划状态被统一纳入控制。

#### 关键优化点
- 版本列表支持更明确的状态展示；
- 版本切换后操作按钮可实时刷新；
- 任务裁剪、任务分解和资源冲突检测等功能与当前版本状态强绑定；
- 通过未保存校验避免版本切换时丢失编辑内容。

#### 对比 `v1.2.2`
- `v1.2.2` 更像是把版本列表和版本配置做出来；
- `v1.3.1` 更强调版本切换后的业务联动和操作约束。

---

## 五、补充的重要公共逻辑

前面的内容已经覆盖了版本主线功能，但要让报告更完整，还需要补上几个项目里真正起支撑作用的公共逻辑。这些内容不一定都由我独立负责，但它们决定了系统是否稳定、是否易维护，属于总结里非常值得体现的部分。

### 1. 请求层统一封装与重复请求取消

#### 代码逻辑说明

项目请求层不仅负责基础的 `baseURL` 和超时配置，还统一完成了请求头注入、版本号上报、token 失效处理、网络异常提示和重复请求取消。对于搜索、分页、联想查询等场景，只有显式开启 `cancelPrevious` 或 `cancelKey` 时才会取消上一笔请求，避免普通业务请求被误伤。

#### 关键代码片段

```ts
// src/utils/request/http.ts
const instance = axios.create({
  baseURL: requestConfig.serverUrl,
  timeout: requestConfig.requestTimeout,
});

instance.interceptors.request.use((config) => {
  const httpConfig = config as InternalHttpRequestConfig;

  // 仅在显式开启时取消上一笔请求，适合搜索框、分页等场景
  if (httpConfig.cancelPrevious || httpConfig.cancelKey) {
    const requestKey = getReqKey(httpConfig);
    const controller = new AbortController();

    if (pendingRequest.has(requestKey)) {
      abortReqKey(requestKey);
    }

    const mergedSignal = mergeAbortSignals([httpConfig.signal, controller.signal]);
    httpConfig.requestKey = requestKey;
    httpConfig.abortController = controller;
    httpConfig.clearAbortSignalListeners = mergedSignal.clear;
    httpConfig.signal = mergedSignal.signal;
    pendingRequest.set(requestKey, controller);
  }

  setHeaders(config);
  return config;
});

instance.interceptors.response.use(
  (res) => {
    clearRequest(res.config);
    if (res.data.code === HttpStatusCode.TOKEN_INVALID) {
      useUserStoreHook().clearToken();
      for (const key of pendingRequest.keys()) {
        abortReqKey(key);
      }
    }
    return Promise.resolve(res.data);
  },
  (error) => {
    clearRequest(error.config);
    if (isCanceledRequest(error)) {
      return Promise.reject(error);
    }
    return Promise.reject(error);
  }
);
```

#### 说明
- 这一层是整个平台请求稳定性的核心；
- `cancelKey` 适合精确控制同一业务线的请求取消；
- token 失效后主动清理队列，可避免旧请求继续污染页面状态。

### 2. 动态路由加载与版本更新容错

#### 代码逻辑说明

系统登录后根据菜单动态注册路由，并在页面切换时统一维护菜单高亮、进度条和页面标题。当版本更新后旧页面仍持有老资源时，动态 import 可能失败，因此路由层增加了异常兜底，触发刷新重新加载最新代码。

#### 关键代码片段

```ts
// src/router/index.ts
router.beforeEach(async (to, from, next) => {
  startNProgress();

  if (!useRouterStoreHook().isMenu || !useUserStoreHook().token) {
    next(['/login', '/500'].includes(to.path) ? undefined : '/login');
    return;
  }

  const isExistRoute = await loadRoutes(to.path);
  const hasRoute = router.hasRoute(<string>to.name);
  if (!hasRoute && isExistRoute) {
    next({ ...to, replace: true });
    return;
  }

  updateProjectPlanTaskDetailBackRoute(to, from);
  handleRouter(to.path);
  next();
});

router.onError((error) => {
  if (/failed(?=.*imported module)/i.test(error)) {
    window.location.reload();
  }
});
```

#### 说明
- 动态菜单和动态路由是一套系统能力，不是单页面逻辑；
- 版本发布后路由容错能显著降低“页面白屏/资源失效”的风险；
- 这部分内容很适合放进总结，因为它体现了工程稳定性意识。

### 3. 计划详情返回路径与未保存状态控制

#### 代码逻辑说明

项目计划任务详情页需要支持“从哪里来，回哪里去”，否则一旦路由被替换就会丢失入口上下文。与此同时，计划编制页面还需要防止在有未保存内容时误切版本或误执行高风险操作。

#### 关键代码片段

```ts
// src/stores/components/router.ts
const detailBackRoute = ref('');

const setDetailBackRoute = (args: string) => {
  detailBackRoute.value = args;
};
```

```ts
// src/router/index.ts
if (to.path === PROJECT_PLAN_TASK_DETAIL_PATH) {
  const shouldRecordBackRoute =
    from.path && !['/', '/login'].includes(from.path) && from.path !== to.path;

  if (shouldRecordBackRoute) {
    routerStore.setDetailBackRoute(from.fullPath);
  } else if (from.path !== to.path) {
    routerStore.setDetailBackRoute('');
  }
}
```

```ts
// src/stores/components/project.ts
const hasUnsavedContent = toRef(() => {
  if (!hasSavePermission.value) {
    return false;
  }
  const changedTasks = projectInstance.value?.getChangedTasks('modified', true);
  const hasChangedTask = (changedTasks || []).length > 0;
  const hasAddTask = projectInstance.value?.getChangedTasks('added')?.length > 0;
  const hasRemoveTask = projectInstance.value?.getRemovedTasks()?.length > 0;
  return activedMenu.value === 'ProjectPlanning' && (hasChangedTask || hasAddTask || hasRemoveTask);
});
```

#### 说明
- 返回路径记录解决的是“详情页返回断链”问题；
- 未保存状态控制解决的是“版本切换/操作误触”问题；
- 这两块虽然不直接产出页面新功能，但对项目体验影响非常大。

### 4. 搜索列表请求取消与最后一次结果生效

#### 代码逻辑说明

在项目选择、联想搜索这类高频输入场景中，旧请求返回可能覆盖新请求结果。项目里通过取消上一笔请求并配合请求序号判断，确保只有最后一次查询结果写入界面。

#### 关键代码片段

```ts
// src/views/project/project-plan/components/SelectProject.vue
const { result } = await projectPlanningApiMap.allProjectListApi(
  {
    id: '',
    keyWord: currentKeyword,
    pageNo: targetPageNo,
    pageSize: PAGE_SIZE,
  },
  {
    cancelPrevious: true,
    cancelKey: REQUEST_CANCEL_KEYS.PROJECT_PROJECT_MANAGE_SELECT_PROJECT_COMP,
  }
);

if (requestId !== projectListRequestId || currentKeyword !== searchKeyword.value) return;
projectList.value = normalizeProjectList(result?.records || []);
```

#### 说明
- 这一逻辑避免了快速输入时的数据回写错乱；
- 请求取消和请求序号双保险，适合写进“技术难点及解决方案”；
- 它能体现项目在交互细节上的工程质量。

## 六、1.2.2 与 1.3.1 的差异与改进总结

### 1. 功能定位不同
- **`v1.2.2`**：以基础模块建设和页面闭环为主，重点是“能用、能查、能改”；
- **`v1.3.1`**：以联动优化和平台增强为主，重点是“更稳、更顺、更易维护”。

### 2. 代码复杂度不同
- **`v1.2.2`** 的代码结构更偏单页面、单流程；
- **`v1.3.1`** 的代码开始考虑跨模块状态、登录触发、定时刷新和版本恢复。

### 3. 用户体验不同
- **`v1.2.2`** 完成基础页面展示和操作入口；
- **`v1.3.1`** 补齐升级公告、路由容错、消息轮询和返回路径等体验细节。

### 4. 稳定性不同
- **`v1.2.2`** 侧重业务正确性；
- **`v1.3.1`** 额外解决了发布后资源失效、旧页面状态残留、公告触达不及时等问题。

---

## 七、开发过程中遇到的技术难点及解决方案

### 1. 动态路由与后端菜单映射复杂
**难点**：菜单层级多，页面路径和组件路径必须严格对应，且需要支持二级、三级菜单和隐藏菜单。

**解决方案**：
- 以菜单 `url` 动态映射到 `src/views` 下对应页面；
- 用递归方式生成路由树；
- 通过白名单和首菜单重定向保证登录后可正常进入。

### 2. 版本更新后页面资源失效
**难点**：前端发布新版本后，用户可能仍停留在旧页面，导致动态 import 失败。

**解决方案**：
- 在路由错误处理中识别模块加载失败；
- 直接触发页面刷新，重新加载最新资源。

### 3. 计划版本切换时状态容易丢失
**难点**：计划版本切换会影响当前任务、操作按钮和详情上下文，稍有不慎就会造成状态错乱。

**解决方案**：
- 切换版本前先检查未保存内容；
- 将版本列表、当前版本、按钮权限和任务实例状态统一联动；
- 通过 store 保存返回路径和当前版本信息。

### 4. 高级查询字段多且复用要求高
**难点**：不同页面都有类似的多条件筛选，但字段、类型和操作符并不完全一致。

**解决方案**：
- 通过高级查询配置对象抽象控件类型；
- 结合业务枚举和字典数据动态生成筛选项；
- 把缓存、回填和查询提交逻辑统一到通用能力中。

### 5. 升级公告与消息中心需要保持一致
**难点**：公告显示、已读回写和消息数刷新需要同步完成，否则会出现提示已关但消息数未变的情况。

**解决方案**：
- 关闭公告时同步调用已读接口；
- 关闭后刷新消息中心未读数；
- 通过登录事件和定时轮询确保公告能被及时拉取。

---

## 八、个人收获与技能提升总结

通过参与 `v1.2.2` 和 `v1.3.1` 两个版本的开发，我在以下方面有了明显提升：

### 1. 前端工程化能力
我对 Vue 3、TypeScript、Pinia、Vue Router、Axios 和 Element Plus 的协同使用更加熟练，能够从请求、状态、路由到页面组件完整梳理业务链路。

### 2. 版本迭代意识
我逐步理解了“功能开发”与“版本发布后稳定性”之间的关系，不再只关注页面是否能展示，还会关注版本切换、资源刷新、路由恢复和公告触达等问题。

### 3. 业务分析能力
在项目计划、预算版本和升级公告等模块中，我学会了从业务对象出发分析字段、状态和权限，而不是只看 UI 层代码。

### 4. 问题定位能力
面对字段缺失、状态残留、动态路由异常、未保存内容丢失等问题，我能通过页面表现、接口返回和代码调用链逐步定位根因。

### 5. 协作与维护意识
我更加重视代码结构、公共能力复用和注释规范，能够在保证现有功能稳定的前提下完成模块迭代，并尽量减少对其他页面的影响。

---

## 九、总结

总体来看，`v1.2.2` 阶段帮助我完成了从“基础业务页面开发”到“版本化业务模块实现”的过渡；`v1.3.1` 阶段则让我进一步参与到“平台稳定性、版本发布联动和用户体验优化”的工作中。

这两个版本的开发经历让我对前端项目的真实工程实践有了更完整的认识：一个功能不仅要写出来，还要能在版本迭代、路由切换、权限控制和异常恢复等场景下持续稳定运行。此次实习不仅提升了我的代码实现能力，也强化了我对系统设计、业务协同和长期维护的理解。
