-- PostgreSQL 初始化脚本

-- 创建必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID生成支持
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- 模糊搜索和全文检索支持

-- 输出初始化信息
DO $$
BEGIN
    RAISE NOTICE '==================================================';
    RAISE NOTICE 'MuMuAINovel PostgreSQL 扩展安装完成';
    RAISE NOTICE '已安装扩展:';
    RAISE NOTICE '  - uuid-ossp: UUID生成支持';
    RAISE NOTICE '  - pg_trgm: 模糊搜索和全文检索支持';
    RAISE NOTICE '';
    RAISE NOTICE '注意:';
    RAISE NOTICE '  - 时区配置: 通过docker-compose.yml的TZ环境变量';
    RAISE NOTICE '  - 字符编码: 通过POSTGRES_INITDB_ARGS配置';
    RAISE NOTICE '  - 表结构: 由SQLAlchemy ORM自动创建';
    RAISE NOTICE '  - 预置数据: 由Python代码init_db()动态插入';
    RAISE NOTICE '==================================================';
END $$;