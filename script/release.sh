# 捕捉异常：遇到错误则停止执行
set -e

if git status --porcelain | grep -q '^[ MARC]'; then # 判断仓库是否干净
  git add .
  git commit -m "update script" # 更新信息
fi

echo "将源码推送到Gitee"
# git remote add gitee git@gitee.com:kimshift/pyScript.git
git push gitee master

echo "将源码推送到Github"
# git remote add github git@github.com:kimshift/pyScript.git
git push github master
# git push github refs/tags/v$version # 提交 tag 到远程仓库
