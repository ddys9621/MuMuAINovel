-- 创建项目数据库和用户
-- 如果用户已存在，先删除
DROP USER IF EXISTS mumuai;

-- 创建用户
CREATE USER mumuai WITH PASSWORD 'mumuai123';

-- 如果数据库已存在，先删除（可选，首次安装不需要）
-- DROP DATABASE IF EXISTS mumuai_novel;

-- 创建数据库
CREATE DATABASE mumuai_novel WITH OWNER mumuai ENCODING 'UTF8';

-- 授予权限
GRANT ALL PRIVILEGES ON DATABASE mumuai_novel TO mumuai;

-- 连接到新数据库并授予 schema 权限
\c mumuai_novel
GRANT ALL ON SCHEMA public TO mumuai;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO mumuai;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO mumuai;

-- 显示成功信息
\echo '✅ 数据库配置完成！'
\echo '数据库名: mumuai_novel'
\echo '用户名: mumuai'
\echo '密码: mumuai123'

