# 捕捉异常：遇到错误则停止执行
set -e

if git status --porcelain | grep -q '^[ MARC]'; then # 判断仓库是否干净
  git add .
  git commit -m "update script" # 更新信息
fi

# 提交命令:npm run release

# 补丁修改---修改小版本
# npm version patch

# 新增功能---修改中版本
# npm version minor

# 重大修改---修改大版本
# npm version major

# version=$(cat package.json | grep version | head -1 | awk -F: '{ print $2 }' | sed 's/[",]//g' | tr -d '[[:space:]]')
# echo "当前最新版本号：'$version'"

echo "将源码推送到Gitee"
git remote add gitee git@gitee.com:kimshift/py-script.git
git push gitee master

echo "将源码推送到Github"
git remote add github git@github.com:kimshift/pyScript.git
git push github master
# git push github refs/tags/v$version # 提交 tag 到远程仓库
