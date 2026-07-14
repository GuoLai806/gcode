## 安装

我们先去到Claude Code官网

<https://code.claude.com/docs/en/overview>

找到这里的安装命令

![]()

我们根据自己的操作系统来选择对应的安装命令，比如我是macOS，就选择第一条

curl -fsSL  <https://claude.ai/install.sh> | bash

如果是windows，我们就选择第二或者第三条

irm  <https://claude.ai/install.ps1> | iex curl -fsSL <https://claude.ai/install.cmd> -o install.cmd && install.cmd && del install.cmd

## 配置模型

### 官方订阅

https://claude.ai/

使用 Claude Code 时，模型首选当然是 Anthropic 自家的 Claude，而最具性价比的方式是直接订阅套餐——对大多数用户来说，每月 $100 的 Max 计划已经足够。如果预算有限，也可以参考下面的国产模型替代方案。

![]()

如果订阅了Claude，只需要在本地终端输入Claude，然后用下面截图第一种方式，网页授权登录即可使用

![]()

### GLM

GLM模型算是比较有性价比的了，而且订阅方式非常方便——<https://www.bigmodel.cn/glm-coding?ic=WQLTOYQV0S>

正常来说订阅一个Lite就够用了

![]()

然后可以到Coding Plan工作台，创建一个Api Key—— <https://bigmodel.cn/coding-plan/personal/overview>

![]()

有了Apikey，建议直接参考GLM官方文档这个方式三来进行手动配置，记得把your\_zhipu\_api\_key替换成刚才创建的

<https://docs.bigmodel.cn/cn/coding-plan/quick-start>

![]()

### DeepSeek

在Claude Code接入DeepSeek也是非常好的选择，可以在这里创建一个Api Key—— <https://platform.deepseek.com/api_keys> ，然后自行进行充值 https://platform.deepseek.com/top\_up  使用，DeepSeek最近价格折扣，还是非常耐用的

![]()

最后就是修改一下你的Claude Code配置，改成使用DeepSeek的，可以参考官方文档完成

<https://api-docs.deepseek.com/zh-cn/quick_start/agent_integrations/claude_code>

![]()

## 测试使用

安装完成后，我们打开终端，输入

claude

就会进入到我们的终端界面了

![]()

我们可以输入一句你好试试

![]()

可以看到，AI会对你进行回答，恭喜你正式开启了AI编程之路！
