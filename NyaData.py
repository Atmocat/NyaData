from flask import Flask,render_template,request
from typing import Optional, Any, List
import os,sys,time,atexit,sqlite3,json,webbrowser,threading


main_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
app = Flask(__name__,
            template_folder=os.path.normpath(os.path.join(main_path,"templates")),
            static_folder=os.path.normpath(os.path.join(main_path,"static")))


def stop():
    os._exit(0)

atexit.register(stop)

def get_gura_day(day: str | None = None) -> int:
    today = day if day else time.strftime("%Y%m%d")
    day_start = time.mktime(time.strptime("20250501","%Y%m%d"))
    day_today = time.mktime(time.strptime(today,"%Y%m%d"))
    duration = (day_today - day_start) // (24*60*60)
    return int(duration)

def get_ad_day(gura_day: str | int | None) -> str:
    if not gura_day:
        return time.strftime("%Y%m%d")
    day_start = time.mktime(time.strptime("20250501","%Y%m%d"))
    duration = int(gura_day) *60*60*24
    day_ad = time.gmtime(day_start + duration)
    return time.strftime("%Y%m%d",day_ad)


class DataManage:
    def __init__(self) -> None:
        self.encode = 'utf-8'
        self.month_day = {"01":31,"02":28,"03":31,"04":30,"05":31,"06":30,"07":31,"08":31,"09":30,"10":31,"11":30,"12":31}
        self.month_list = ["01","02","03","04","05","06","07","08","09","10","11","12"]
        self.path = os.path.normpath(os.path.join(main_path,"data"))
        if not os.path.exists(self.path):
            os.makedirs(self.path,exist_ok=True)
        self.today = time.strftime("%Y%m%d")
        self.main_data = {}
        self.get_main_data()
        try:
            self.db = sqlite3.connect(
                f"file:{os.path.normpath(os.path.join(self.path, 'main.db'))}?mode=ro",
                uri=True,
                check_same_thread=False
            )
        except Exception:
            stop()
        self.cursor = self.db.cursor()
    
    def get_main_data(self):
        try:
            main_file_path = os.path.normpath(os.path.join(self.path,"main.json"))
            with open(main_file_path,"r",encoding=self.encode) as f:
                self.main_data = json.load(f)
        except FileNotFoundError:
            stop()
        except Exception as e:
            self.is_ok = False
    
    def get_song(self, song_name: str) ->dict | None:
        """
        读取指定song的所有数据，返回该song行的所有字段内容。
        :param song_name: 歌曲名(非路径)
        :return: dict 或 None（未找到时）
        """
        try:
            self.cursor.execute("SELECT * FROM songs WHERE SongName = ?", (song_name,))
            self.db.commit()
            row = self.cursor.fetchone()
            if row:
                columns = [desc[0] for desc in self.cursor.description]
                info = dict(zip(columns, row))
                return info
            else:
                return None
        except Exception as e:
            print(f"在获取歌曲[{song_name}]数据时发生[{e}]错误")
            return None
        
    def get_song_list(self,star_day: str, end_day: str) -> dict | None:
        """
        获取[star_day,end_day]日期段内的所有歌曲数据\n
        -> dict | None\n
        "song_name":[播放次数,循环播放次数]
        ""star_day"和"end_day"均为AD Day
        """
        try:
            start_day_gura = get_gura_day(star_day)
            end_day_gura = get_gura_day(end_day)
            if not os.path.exists(os.path.normpath(os.path.join(self.path,"Days"))):
                os.makedirs(self.path,exist_ok=True)
                return None
            output = {}
            for day in range(start_day_gura,end_day_gura+1):
                day_data = self.get_day_data(day)
                if not day_data:
                    continue
                song_data: dict|None = day_data.get("song",None)
                if not song_data:
                    continue
                for song_name in song_data.keys():
                    if output.get(song_name,None) is None:
                        output[song_name] = song_data[song_name]
                    else:
                        output[song_name][0] += song_data[song_name][0]
                        output[song_name][1] += song_data[song_name][1]
            return output
        except Exception as e:
            print(f"在获取[{star_day} - {end_day}]日期段内的歌曲数据时发生[{e}]错误")
            return None
        
    def get_all_data(self) ->list[list] | None:
        """
        获取所有歌曲数据\n
        -> list[list] | None
        """
        try:
            self.cursor.execute("SELECT * FROM songs")
            row = self.cursor.fetchall()
            return [list(rows) for rows in row]
        except Exception as e:
            print(f"在获取所有数据时发生[{e}]错误")
            return None
    
    def get_day_data(self,gura_day: int) ->dict | None:
        """
        获取日听歌数据文件\n
        ->dict | None
        """
        try:
            with open(os.path.normpath(os.path.join(self.path,f"Days/{gura_day}.json")),encoding=self.encode) as file:
                data = json.load(file)
                if not data.get("all",0):
                    return None
                return data
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"在读取[{gura_day}.json]时出现错误[{e}]")

    def get_artist_song(self,artist: str) -> list[str] | None:
        all_data = self.get_all_data()
        if all_data is None:
            return None
        output = []
        for info in all_data:
            if artist in info[2]:
                output.append(info[0])
        return output

    def get_most_play_day(self,song_name: str,start_day: str|None = None, end_day: str|None = None) -> tuple | None:
        """
        day: AD day\n
        -> tuple(播放次数最多,循环播放最多)[Gura Day] | None
        """
        duration = [0,get_gura_day()]
        most_loop,most_play = 0,0
        most_loop_day,most_play_day = [],[]
        if start_day is not None:
            duration[0] = get_gura_day(start_day)
        if end_day is not None:
            duration[1] = get_gura_day(end_day)
        if not os.path.exists(os.path.normpath(os.path.join(self.path,"Days"))):
            os.makedirs(self.path,exist_ok=True)
            return None
        for day in range(duration[0],duration[1]+1):
            day_data = self.get_day_data(day)
            if not day_data:
                continue
            song_data: dict|None = day_data.get("song",None)
            if not song_data:
                continue
            song: list = song_data.get(song_name,None)
            if not song:
                continue
            if song[0] > most_play:
                most_play_day = []
                most_play_day.append(day)
                most_play = song[0]
            elif song[0] == most_play:
                most_play_day.append(day)
            if song[1] > most_loop:
                most_loop_day = []
                most_loop_day.append(day)
                most_loop = song[1]
            elif song[1] == most_loop:
                most_loop_day.append(day)
        
        return (most_play_day,most_loop_day)

    def get_song_weight(self, song_name: str, start_day: str | None = None, end_day: str | None = None) -> float | None:
        """
        传入起止日期均为AD Day
        """
        FAVOUR_C = 1000
        day = get_gura_day()                     # 当前AD Day
        day_ad = int(time.time())                # 当前时间戳(用于错误处理时的默认值)

        # 确定统计区间 [start, end] 的AD Day
        start = 0
        end = day
        if start_day is not None:
            start = get_gura_day(start_day)
        if end_day is not None:
            end = get_gura_day(end_day)

        # ---------- 全量数据（无起止日期）----------
        if start == 0 and end == day:
            info = self.get_song(song_name)
            if info is None:
                return None
            loop_count = info.get("LoopCount", 0)
            play_count = info.get("PlayCount")
            if play_count is None:
                return None
            # 获取末次播放的AD Day
            last_play_ad = info.get("LastPlay", day_ad)
            last_play = get_gura_day(time.strftime("%Y%m%d", time.localtime(last_play_ad)))

            # 公式计算
            if play_count == 0:
                return None
            weight = FAVOUR_C * (play_count + loop_count) * (last_play / day)
            return weight

        # ---------- 指定时间段 ----------
        total_play = 0
        total_loop = 0
        last_play = start               # 初始化为区间起点，后续会被更新为实际最后播放日
        # 遍历区间内每一天
        for d in range(start, end + 1):
            day_data = self.get_day_data(d)
            if not day_data:
                continue
            song_data = day_data.get("song")
            if not song_data:
                continue
            song_info = song_data.get(song_name)
            if not song_info:
                continue
            total_play += song_info[0]   # 播放次数
            total_loop += song_info[1]   # 循环次数
            last_play = d                # 最后播放日（越往后越大，最后一次赋值即区间内最大日期）

        if total_play == 0:
            return None

        # 新鲜度因子：用区间内的最后播放日 除以 区间结束日
        freshness = last_play / end
        weight = FAVOUR_C * (total_play + total_loop) * freshness
        return weight
    
    def get_artist_weight(self, artist_name: str, start_day: str | None = None, end_day: str | None = None) -> float | None:
        """
        传入起止日期均为AD Day\n
        -> float | None
        """
        FAVOUR_C = 1000
        day = get_gura_day()                     # 当前AD Day
        day_ad = int(time.time())                # 当前时间戳(用于错误处理时的默认值)

        # 确定统计区间 [start, end] 的AD Day
        start = 0
        end = day
        if start_day is not None:
            start = get_gura_day(start_day)
        if end_day is not None:
            end = get_gura_day(end_day)

        if start == 0 and end == day:
            song_list = self.get_artist_song(artist_name)
            if song_list is None or len(song_list) == 0:
                return None
            total_weight = 0.0
            valid_songs = 0 # 歌曲总数
            for song in song_list:
                weight = self.get_song_weight(song)
                if weight is not None:
                    total_weight += weight
                    valid_songs += 1
            if valid_songs == 0:
                return None
            artist_weight = total_weight / valid_songs
            return artist_weight
        
        # 获取歌手的所有歌曲列表
        song_list = self.get_artist_song(artist_name)
        if song_list is None or len(song_list) == 0:
            return None

        total_weight = 0.0
        valid_songs = 0 # 总歌曲数(区间内)

        for song in song_list:
            weight = self.get_song_weight(song, start_day, end_day)
            if weight is not None:
                total_weight += weight
                valid_songs += 1

        if valid_songs == 0:
            return None

        # 歌手权重为其所有歌曲权重的平均值
        artist_weight = total_weight / valid_songs
        return artist_weight
    
    def get_most_favourite_artist(self, start_day: str | None = None, end_day: str | None = None) -> str | None:
        """
        获取最喜爱歌手\n
        传入起止日期均为AD Day\n
        -> str | None
        """
        
        day = get_gura_day()

        start = 0
        end = day
        if start_day is not None:
            start = get_gura_day(start_day)
        if end_day is not None:
            end = get_gura_day(end_day)

        if start == 0 and end == day:
            song_list = self.get_all_data()
            if song_list is None:   
                return None
            artist_weights = {}
            for song_info in song_list:
                artist_name = song_info[2] # str
                if ";" in artist_name:
                    artist_name = artist_name.split(";") # 多歌手 # list

                # 多歌手
                if isinstance(artist_name, list):
                    for name in artist_name:
                        weight = self.get_song_weight(song_info[0])
                        if weight is not None:
                            if name not in artist_weights:
                                artist_weights[name] = []
                            artist_weights[name].append(weight)
                    continue
                
                # 单歌手
                weight = self.get_song_weight(song_info[0])
                if weight is not None:
                    if artist_name not in artist_weights:
                        artist_weights[artist_name] = []
                    artist_weights[artist_name].append(weight)
            
            # 计算每个歌手的平均权重
            average_weights = {}
            for artist, weights in artist_weights.items():
                if weights:
                    average_weights[sum(weights) / len(weights)] = artist
            if not average_weights:
                return None
            
            # 取最大值
            max_weight = max(average_weights.keys())
            # 找到具有最大平均权重的歌手
            return average_weights.get(max_weight, None)
    
        # 区间内计算逻辑
        song_list = self.get_song_list(get_ad_day(start), get_ad_day(end))
        if song_list is None:
            return None
        artist_weights = {}
        for song_name, play_info in song_list.items():
            artist_name = self.get_song(song_name)

            if artist_name is None:
                continue
            
            artist_name = artist_name.get("Artist", None)

            if artist_name is None:
                continue

            if ";" in artist_name:
                artist_name = artist_name.split(";") # 多歌手 # list

            # 多歌手
            if isinstance(artist_name, list):
                for name in artist_name:
                    weight = self.get_song_weight(song_name, get_ad_day(start), get_ad_day(end))
                    if weight is not None:
                        if name not in artist_weights:
                            artist_weights[name] = []
                        artist_weights[name].append(weight)
                continue
            
            # 单歌手
            weight = self.get_song_weight(song_name, get_ad_day(start), get_ad_day(end))
            if weight is not None:
                if artist_name not in artist_weights:
                    artist_weights[artist_name] = []
                artist_weights[artist_name].append(weight)
            
        # 计算每个歌手的平均权重
        average_weights = {}
        for artist, weights in artist_weights.items():
            if weights:
                average_weights[sum(weights) / len(weights)] = artist
        if not average_weights:
            return None
        
        # 取最大值
        max_weight = max(average_weights.keys())
        # 找到具有最大平均权重的歌手
        return average_weights.get(max_weight, None)

    def get_most_favourite_song(self, start_day: str | None = None, end_day: str | None = None) -> str | None:
        """
        获取最喜爱歌曲\n
        传入起止日期均为AD Day\n
        -> str | None
        """
        day = get_gura_day()

        start = 0
        end = day
        if start_day is not None:
            start = get_gura_day(start_day)
        if end_day is not None:
            end = get_gura_day(end_day)
        
        # 获取总数据的最喜欢歌曲
        if start == 0 and end == day:
            song_list = self.get_all_data()
            if song_list is None:
                return None
            
            max_weight = -1
            favourite_song = None

            for song_info in song_list:
                song_name = song_info[0]
                weight = self.get_song_weight(song_name)
                if weight is not None and weight > max_weight:
                    max_weight = weight
                    favourite_song = song_name
            
            return favourite_song

        song_list = self.get_song_list(get_ad_day(start), get_ad_day(end))
        if song_list is None:
            return None
        
        max_weight = -1
        favourite_song = None

        for song_name in song_list.keys():
            weight = self.get_song_weight(song_name, get_ad_day(start), get_ad_day(end))
            if weight is not None and weight > max_weight:
                max_weight = weight
                favourite_song = song_name
        
        return favourite_song


class ShowData(DataManage):
    def __init__(self) -> None:
        super().__init__()
    def index_data(self) ->list:
        """
        获取主页数据\n
        -> tuple\n
        [0] 今年年份\n
        [1] 总播放时长\n
        [2] 年内月播放时长(list)
        """
        if not self.main_data:
            stop()
        
        data: list = []
        year = self.today[:4]
        data.append(year)
        data.append(self.main_data["all"]//(60*60))
        month_data:list = []
        for month in self.month_list: # 获取12个月份
            month_data_get = self.main_data["month"].get(f"{year}{month}",0) // (60 * 60)
            month_data.append([month,month_data_get])
        
        data.append(month_data)
        return data

    def song_data(self,song_name) ->list | None:
        """
        获取指定歌曲数据\n
        ->list\n
        [0] 歌名\n
        [1] 时长\n
        [2] 作家\n
        [3] 播放次数\n
        [4] 单曲循环次数\n
        [5] 第一次播放日期\n
        [6] 上次播放日期\n
        [7] 播放最多的一天\n
        [8] 循环播放最多的一天
        """
        data = self.get_song(song_name)
        if not data:
            return None
        list_data = []
        for _ in data.keys():
            list_data.append(data.get(_,None))
        most_play = self.get_most_play_day(song_name)
        list_data.extend([None,None])
        if not most_play:
            return list_data
        list_data[5] = time.strftime("%Y%m%d",time.localtime(list_data[5]))
        list_data[6] = time.strftime("%Y%m%d",time.localtime(list_data[6]))
        for __ in range(len(most_play[0])):
            most_play[0][__] = get_ad_day(most_play[0][__])
        for __ in range(len(most_play[1])):
            most_play[1][__] = get_ad_day(most_play[1][__])
        list_data[7],list_data[8] = most_play[0],most_play[1]
        return list_data
    
    def day_data(self,ad_day: str) -> tuple | None:
        """
        获取单日听歌数据\n
        -> tuple | None\n
        (总听歌时长,当日播放总时长,当日听歌曲目数)
        """

        output = [0,0,0]
        day_info = self.get_day_data(get_gura_day(ad_day))
        output[0] = self.main_data.get("all",0)
        if day_info is not None:
            output[1] = day_info.get("all",0)
            output[2] = len(day_info.get("song",{}))
        return tuple(output)

    def all_song_data(self) -> list[list] | None:
        """
        获取所有歌曲数据\n
        -> list[tuple] | None
        """
        data = self.get_all_data()
        if data is None:
            return None
        for info in data:
            if info[5]:
                info[5] = time.strftime("%Y%m%d",time.localtime(info[5]))
            if info[6]:
                info[6] = time.strftime("%Y%m%d",time.localtime(info[6]))
        
        return data

    def artist_data(self,artist_name: str) ->list |None:
        """
        [0]:作家名\n
        [1]:所有歌曲列表 [歌名,单曲时长,总播放次数,第一次播放时间(AD)]\n
        [2]:最喜欢的3首歌 [歌名,歌名,歌名]\n
        [3]:第一次听该歌手的日期\n
        [4]:听该歌手时长
        """
        song_list = self.get_artist_song(artist_name)
        if song_list is None:
            return None
        output_song_list = []
        favour_song = {}
        output_duration = 0
        day = get_gura_day()
        first_play_time = day

        for song_name in song_list:
            song_info = self.get_song(song_name)
            if song_info is None:
                continue
            output_duration += song_info.get("PlayCount",0) * song_info.get("Duration",0)
            first_time = song_info.get("FirstPlay",None)
            if first_time is not None:
                first_time = time.strftime("%Y%m%d",time.localtime(first_time))
            output_song_list.append([song_name,song_info.get("Duration",None),song_info.get("PlayCount",None),first_time])
            song_weight = self.get_song_weight(song_name)
            if len(favour_song) < 3 and (song_weight is not None):
                favour_song[song_name] = song_weight
            elif song_weight is not None:
                change_key = None
                for old_info in favour_song.keys():
                    if favour_song[old_info] < song_weight:
                        change_key = old_info
                        break
                if change_key is not None:
                    favour_song.pop(change_key)
                    favour_song[song_name] = song_weight
            
            old_first_play = song_info.get("FirstPlay",None)
            if old_first_play is None:
                continue
            old_first_play = get_gura_day(time.strftime("%Y%m%d",time.localtime(old_first_play)))
            if first_play_time > old_first_play:
                first_play_time = old_first_play
        
        output_favour_song = [name for name in favour_song.keys()]
        return [artist_name,output_song_list,output_favour_song,get_ad_day(first_play_time),output_duration]
    
    def year_data(self,year: str) -> tuple | None:
        """
        year: 年份\n
        -> tuple | None\n
        (year_eachMonth, year_time, year_favourite)\n
        """

        # 数据:        
        # year_eachMonth    月听歌总时长,月听歌曲目数,[最喜爱歌曲,月播放次数,月播放最多日],月最喜爱歌手    字典,每月为键
        # year_time    总播放时长,总听歌曲目数,本年播放总时长,本年听歌曲目数    列表
        # year_favourite    [全年最喜爱歌曲,播放最多日],[全年循环最多歌曲,循环最多日],全年最喜爱歌手    嵌套列表

        year_eachMonth = {}
        year_time = [0,0,0,0]
        year_favourite = [[None,None],[None,None],None]

        # 填充year_eachMonth数据
        for month in self.month_list:
            output = [0,0,[None,0,None],None]
            month_key = f"{year}{month}"
            month_time = self.main_data["month"].get(month_key,0)
            output[0] = month_time

            month_end_day = self.month_day[month]
            if month == "02":
                month_end_day = 29 if int(year) % 4 == 0 else 28

            month_song_data = self.get_song_list(f"{year}{month}01",f"{year}{month}{month_end_day}")

            #处理未获取数据的情况
            if month_song_data is None:
                year_eachMonth[month] = output
                continue

            month_song_count = len(month_song_data) #月听歌总数据
            output[1] = month_song_count

            #获取月最喜欢歌曲
            most_favourite_song_info: List[Optional[Any]] = [None, None, None]  # 歌名,月播放次数,月播放最多日

            most_favourite_song = self.get_most_favourite_song(f"{year}{month}01",f"{year}{month}{month_end_day}")
            if most_favourite_song is not None:
                most_favourite_song_info[0] = most_favourite_song
                most_favourite_song_info[1] = month_song_data.get(most_favourite_song,[0,0])[0]
                most_play_day = self.get_most_play_day(most_favourite_song,f"{year}{month}01",f"{year}{month}{month_end_day}")
                if most_play_day is not None and len(most_play_day[0]) > 0:
                    most_favourite_song_info[2] = most_play_day[0][0]
            output[2] = most_favourite_song_info
            output[3] = self.get_most_favourite_artist(f"{year}{month}01",f"{year}{month}{month_end_day}")
            year_eachMonth[month] = output
        
        year_song_list = self.get_song_list(f"{year}0101",f"{year}1231")
        # 填充year_time数据
        year_time[0] = self.main_data.get("all",0)
        all_data = self.get_all_data()
        if all_data is not None:
            year_time[1] = len(all_data)
        year_info = self.main_data.get("year",None)
        if year_info is not None:
            year_time[2] = year_info.get(year,0)
        year_time[3] = len(year_song_list) if year_song_list is not None else 0

        # 填充year_favourite数据
        year_most_favourite_song = self.get_most_favourite_song(f"{year}0101",f"{year}1231")
        if year_most_favourite_song is not None:
            year_favourite[0][0] = year_most_favourite_song

            year_most_favourite_song_play_day = self.get_most_play_day(year_most_favourite_song,f"{year}0101",f"{year}1231")
            if year_most_favourite_song_play_day is not None and len(year_most_favourite_song_play_day[0]) > 0:
                year_favourite[0][1] = year_most_favourite_song_play_day[0][0]
        
        year_most_loop = -1
        year_most_loop_song = None
        if year_song_list is not None:
            for song_name, play_info in year_song_list.items():
                if play_info[1] > year_most_loop:
                    year_most_loop = play_info[1]
                    year_most_loop_song = song_name
        year_favourite[1][0] = year_most_loop_song
        year_favourite[1][1] = year_most_loop
        year_favourite[2] = self.get_most_favourite_artist(f"{year}0101",f"{year}1231")
    
        return (year_eachMonth, year_time, year_favourite)

Show = ShowData()

@app.route("/")
def index():
    data = Show.index_data()
    return render_template("NyaData.html", all_data = data)

@app.route("/day")
def days():
    ad_day = request.args.get("day")
    if not ad_day: # 未获取到url中的日期 全部返回空值
        return render_template("NyaDay.html",all_data = None)
    data = Show.day_data(ad_day)
    if data is None:
        return render_template("NyaDay.html",all_data = None)
    
    return render_template("NyaDay.html",all_data = data)

@app.route("/song")
def song():
    song_name = request.args.get("songname")
    if not song_name:
        return render_template("NyaSong.html",song_data= [None for __ in range(9)])
    data = Show.song_data(song_name)
    return render_template("NyaSong.html",song_data= data)


@app.route("/AllSong")
def AllSong():
    data = Show.all_song_data()
    # 如果是空值就返回空值本身
    return render_template("NyaAll.html",foreverLove = data)

@app.route("/artist")
def Artist():
    artist_name = request.args.get("artist")
    if artist_name is None:
        return render_template("NyaArtist.html",artistsTotal = None)
    data_list = Show.artist_data(artist_name)
    return render_template("NyaArtist.html",artistsTotal = data_list)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/year")
def year():
    year = request.args.get("year")
    if not year:
        return render_template("NyaYear.html",year_eachMonth = None, year_time = None, year_favourite = None)
    data = Show.year_data(year)
    if data is None:
        return render_template("NyaYear.html",year_eachMonth = None, year_time = None, year_favourite = None)
    return render_template("NyaYear.html",year_eachMonth = data[0], year_time = data[1], year_favourite = data[2])



def open_browser():
    webbrowser.open_new("http://127.0.0.1:1812/")
    # pass

def main():
    threading.Timer(1, open_browser).start()
    app.run(port=1812)

if __name__ == "__main__":
    main()