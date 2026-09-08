# 公开 CI 输入

此目录尚无 READY。全部新生成答案需要人工审核，不能将草案作为 CI 放行凭证。

审核场景、确认样本可公开后执行：

```sh
python3 benchmark/scripts/release_acceptance.py snapshot export --output ci-input/current
python3 benchmark/scripts/release_acceptance.py snapshot validate --snapshot ci-input/current
```

每次导出使用新目录，保留旧快照后再更新 current。对象基于内容 SHA-256 定位，脱离本地源路径仍可复现。源文件私有、答案未批准、证据校验不通过时，正式导出失败。`--allow-draft` 仅供检查，私有原件不导出，也不生成 READY。
