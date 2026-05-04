# Secrets 使用说明

本目录用于存放 Docker Compose 运行时读取的敏感信息文件。

## 必需文件

1. `local_auth_password.txt`
   - 内容：本地管理员密码（仅一行）

## 快速创建（PowerShell）

```powershell
New-Item -ItemType Directory -Force secrets | Out-Null
Set-Content -Path secrets/local_auth_password.txt -Value "请替换为强密码"
```

## 快速创建（Linux/macOS）

```bash
mkdir -p secrets
echo "请替换为强密码" > secrets/local_auth_password.txt
chmod 600 secrets/local_auth_password.txt
```

## 安全建议

- 不要将真实密码提交到 Git 仓库。
- 生产环境请使用高强度随机密码。
- 如密码泄露，请立即轮换并重启相关服务。
