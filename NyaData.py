from flask import Flask,render_template,request
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

    def get_song_weight(self,song_name: str,start_day: str|None = None, end_day: str|None = None) -> float | None:
        """
        传入起止日期均为AD Day
        """
        FAVOUR_C = 1000
        day = get_gura_day()
        day_ad = int(time.time())
        duration = [0,day]
        if start_day is not None:
            duration[0] = get_gura_day(start_day)
        if end_day is not None:
            duration[1] = get_gura_day(end_day)

        if duration == [0,day]:
            info = self.get_song(song_name)
            if info is None:
                return None
            loop_count = info.get("LoopCount",0)
            play_count = info.get("PlayCount",None)
            if play_count is None:
                return None
            first_play = get_gura_day(time.strftime("%Y%m%d",time.localtime((info.get("FirstPlay",day_ad)))))
            last_play = get_gura_day(time.strftime("%Y%m%d",time.localtime(info.get("LastPlay",day_ad))))
            weight = FAVOUR_C * play_count * last_play / day / first_play * (loop_count / play_count +1)
            return weight
        
        #处理日期段内的weight
        loop_count,play_count,first_play,last_play = 0,0,duration[1],duration[0]
        day = duration[1]
        for days in range(duration[0],duration[1]+1):
            day_data = self.get_day_data(days)
            if not day_data:
                continue
            song_data: dict|None = day_data.get("song",None)
            if not song_data:
                continue
            song: list = song_data.get(song_name,None)
            if not song:
                continue

            if first_play > days:
                first_play = days
            last_play =days
            play_count += song[0]
            loop_count += song[1]
        
        if play_count == 0:
            return None
        first_play = get_gura_day(time.strftime("%Y%m%d",time.localtime(first_play)))
        last_play = get_gura_day(time.strftime("%Y%m%d",time.localtime(last_play)))
        weight = FAVOUR_C * play_count * last_play / day / first_play * (loop_count / play_count +1)
        return weight

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
        print(list_data)
        return list_data
    
    def day_data(self,ad_day: str) -> dict | None:
        """
        获取单日听歌数据\n
        -> dict | None\n
        "all": [int] 听歌时长\n
        "song": [dict] "song_name" : [list] [播放次数,循环播放次数]
        """
        day = get_gura_day(ad_day)
        return self.get_day_data(day)
    
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
        

Show = ShowData()


@app.route("/")
def index():
    data = Show.index_data()
    return render_template("NyaData.html", all_data = data)

@app.route("/day")
def days():
    ad_day = request.args.get("day")
    if not ad_day: # 未获取到url中的日期 全部返回空值
        return render_template("NyaDay.html",day_total = None, day_each = None)
    data = Show.day_data(ad_day)
    if not data or (data.get("all",0)//60) < 1 : # 没有数据或者听歌时长小于1min时 #传值None
        return render_template("NyaDay.html",day_total = None, day_each = None)
    return render_template("NyaDay.html", day_total = data.get("all",0) // 60, day_each = data.get("song",None))

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
    print(data)
    return render_template("NyaAll.html",foreverLove = data)

@app.route("/artist")
def Artist():
    artist_name = request.args.get("artist")
    if artist_name is None:
        return render_template("NyaArtist.html",artistsTotal = None)
    data_list = Show.artist_data(artist_name)
    return render_template("NyaArtist.html",artistsTotal = data_list)

def open_browser():
    webbrowser.open_new("http://127.0.0.1:1812/")
    # pass

def main():
    threading.Timer(1, open_browser).start()
    app.run(port=1812)

if __name__ == "__main__":
    main()