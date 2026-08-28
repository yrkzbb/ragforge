from app.services.chunking import parent_child_chunks

def test_parent_child_and_breadcrumb():
    text="# 安装\n"+("系统 配置 数据库。"*300)+"\n## Linux\n"+("执行 命令 完成 部署。"*200)
    chunks=parent_child_chunks(text,"运维手册",parent_size=60,child_size=20,overlap=5)
    parents=[x for x in chunks if x.level=="parent"];children=[x for x in chunks if x.level=="child"]
    assert len(parents)>1 and len(children)>len(parents)
    assert all(x.parent_ordinal is not None for x in children)
    assert any("安装" in x.breadcrumb for x in chunks)

