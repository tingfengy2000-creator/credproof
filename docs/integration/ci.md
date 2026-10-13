# CI 接入（契约 C）

从 A+B 固定基线 a5b51e303315dd2dd3f4671d7a771fb9afab0310 实现。
本页先记录实现方案；托管运行的完成状态以 evidence/ci-c/README.md 为准。
不调用模型，不发布镜像，不改变安全判定。只支持 Ubuntu 24.04 x86_64。

## GitHub 拉取请求

`.github/workflows/credproof.yml` 只响应 pull_request，两个独立 job 使用
ubuntu-24.04。权限仅 contents:read、security-events:write；动作使用固定提交。
目标由 `.credproof/targets.txt` 的相对配置路径决定。实际检查使用当前提交
构建并安装的 wheel，不以源码目录遮蔽安装来源。

各条命令先留下退出码、stdout、stderr 和原报告，随后上传构件，最后执行
闸门。PASS=0、FAIL=2、UNKNOWN=3、配置/准备错误=4；非 PASS 不放行。
两种 job 均生成 JSON、JUnit、摘要和 SARIF。只有 container 上传 Code
Scanning，每个配置的 automationDetails.id 独立；上传失败不改变检查结论。
摘要同时写入 job summary。未发送任何模型请求。

### AppArmor 选择及边界

本工作流显式选择契约 §2.3 允许的 **外层 AppArmor unconfined** 容器选项，
不会失败后自动切换；不宣称外层仍受 AppArmor 约束。seccomp 使用固定候选
profile，保留 clone3 的 ENOSYS 回退；仍为非 root、cap-drop ALL、
no-new-privileges、network none、read-only，有限 rootfs 由内层 bwrap 提供。
`deploy/apparmor/credproof-bwrap` 的宿主强制执行仍单列为待验证选项。
Ubuntu 的 unconfined 进程创建 userns 时仍可能进入 unprivileged_userns。
因此宿主同时为容器内那个固定 bwrap 可执行路径加载 userns 应用例外，
这是明确记录的外层放宽，不是限定 profile 已通过的证明。

native 仅为 `/opt/credproof-ci-runtime/isolation/tools/usr/bin/bwrap` 这个可信
执行文件加载 userns 许可 profile（unconfined 应用例外），不改变宿主 sysctl，
不为受测项目直接授予宿主访问。记录限制值、实际 profile 和拒绝日志。

### 冻结锚点与演示分开

16 个锚点的输入固定取自上述 A+B 提交；程序固定为本次实际 checkout 提交。
`verify-anchors --source` 核对安装模块，`--anchors-source/--anchors-commit`
单独标记冻结数据。演示 PR 修改 b07 时，不把修改后的入口当成旧漏洞锚点。
两条独立演示 PR 均提向专用演示 base，不合并、不触碰主线。
漏洞版逐字节使用既有原版；参考修复由人工参考源码提供，不称 AI 新修复。
只说明一红一绿，不能说明告警关闭或全项目安全。

### 镜像与隐私

Dockerfile 固定 Ubuntu 基础镜像摘要，从同一源码提交构建，记录 wheel、apt、
rootfs 清单与源码摘要。镜像只在 runner 构建，不推送镜像仓库。
docker export 后完整逐成员扫描。超时/超限为 SCAN_INCOMPLETE，不能算零命中。
例外必须绑定文件、文件摘要、匹配摘要和明确原因；不能按整目录跳过。
当前例外目录有 2,921 个精确条目，用于公开分发包的法律联系信息、路径示例、
格式字符串误匹配及通用 runner 程序标识；真实作者路径不豁免，而是移除不用的
镜像构建输入。报告同时公开已审阅命中次数，不把豁免写成“没有任何模式命中”。
源码/分发文件变化会令精确条目失效；不会自动生成新的豁免。
同一扫描器另扫实际 SARIF/JUnit/摘要。扫描还接收 runner 环境中的仓库 owner，
仅存在临时私有值文件，不把实际账号写进工作流、镜像或扫描收据。
原始命令输出的确定宿主字段会作精确替换，保留脱敏说明，不重写代码或判决。

## GitLab CI 通用片段（未实测）

需要预先安装 Docker、经确认的固定镜像和宿主隔离权限。本片段仅演示
单个目标的退出码保存及 JUnit 构件，不能替代托管 runner 正式验收。

```yaml
credproof:
  script:
    - mkdir -p out && chmod 777 out
    - >-
      docker run --rm --network none --read-only --tmpfs /tmp:exec
      --cap-drop ALL --security-opt no-new-privileges
      --security-opt seccomp=deploy/docker/seccomp-credproof.json
      --security-opt systempaths=unconfined --security-opt apparmor=unconfined
      -v "$CI_PROJECT_DIR:/workspace:ro" -v "$CI_PROJECT_DIR/out:/out"
      credproof:0.3.0.dev38 check --config /workspace/examples/bench/b07-webhook-relay/project/credproof.toml
      --source-root /workspace --output /out/report.json --junit /out/junit.xml
      --sarif /out/report.sarif --summary /out/summary.md > out/stdout.txt 2> out/stderr.txt
      && echo 0 > out/exit.txt || echo $? > out/exit.txt
    - cat out/summary.md
    - test "$(cat out/exit.txt)" = 0
  artifacts:
    when: always
    paths: [out/]
    reports:
      junit: out/junit.xml
```

## Jenkins 通用片段（未实测）

使用上面同样的已确认 Docker 运行参数；不要使用 privileged 或宿主网络。
`returnStatus` 保存实际检查退出码，post always 发布 JUnit 和原报告。

```groovy
pipeline {
  agent { label 'ubuntu-24.04-docker' }
  stages {
    stage('CredProof') {
      steps {
        script {
          def code = sh(returnStatus: true, script: './ci-check-config.sh')
          writeFile file: 'out/exit.txt', text: "${code}\n"
          if (code != 0) { error("CredProof non-PASS (${code})") }
        }
      }
    }
  }
  post { always {
    junit allowEmptyResults: false, testResults: 'out/junit.xml'
    archiveArtifacts artifacts: 'out/**', allowEmptyArchive: false
  } }
}
```

其中 ci-check-config.sh 需要使用上一段的显式 docker 参数；这不是已提供或
实测的 Jenkins 插件。CI 报告仅对应配置声明和实际执行的场景。
