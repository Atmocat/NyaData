# NyaData
![Hello](./static/img/nyadata.ico)  

配合NyaNyaMusicPlayer的数据统计展示程序  

__[NyaNyaMusicPlayer-GUI](https://github.com/Wan-Xing-Star/NyaNyaMusicPlayer-GUI)__  

__[NyaNyaMusicPlayer](https://github.com/Wan-Xing-Star/NyaNyaMusicPlayer)__

# 权重计算
## 歌曲权重公式
__旧公式(v0.1.0<=)__  

    权重 = 1000 × 播放次数 × 最后播放日 ÷ 当前日 ÷ 首次播放日 × (循环次数 ÷ 播放次数 + 1)  

__新公式(v0.1.1>=)__  

    权重 = 1000 × (播放次数 + 循环次数) × (最后播放日 ÷ 当前日)  

## 歌手权重公式
> v0.1.1版本后引入  

    权重 = 歌手所有歌曲权重的平均值