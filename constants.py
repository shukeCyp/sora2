from version import __version__ as APP_VERSION

# 域名
API_HOST = "api.shaohua.fun"
API_BASE_URL = "https://api.shaohua.fun"
# 微信号
WECHAT_ID = "zhaxinyu--"
# gitee仓库地址
GITEE_REPO_URL = "https://gitee.com/shuk513/sora2"
# gitee仓库最新release api    只需要修改shuke/sora2    这个在仓库地址里面直接复制替换就行
GITEE_LATEST_RELEASE_API = "https://gitee.com/api/v5/repos/shuk513/sora2/releases/latest"

API_CHAT_COMPLETIONS_URL = f"{API_BASE_URL.rstrip('/')}/v1/chat/completions"
FILES_ENDPOINT = f"{API_BASE_URL.rstrip('/')}/v1/files"
DISPLAY_API_PROXY_URL = API_BASE_URL
GITEE_RELEASES_URL = f"{GITEE_REPO_URL}/releases"

