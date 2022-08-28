from datetime import datetime, time, timedelta,timezone

import dateutil.parser
import tweepy
import boto3

import os

# AWS---------------------------------

def init_dynamodb():
    table = boto3.resource("dynamodb",
    aws_access_key_id=os.environ.get('AWS_IAM_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_IAM_SECRET_ACCESS_KEY'),
    region_name='ap-northeast-1').Table("progress_bot")
    return table

# DynamoDBからデータを取得する
def get_item_to_dynamodb(table, username: str):
    response = table.get_item(Key={'id': 0, 'username': username})
    print(response)
    if not "Item" in response:
        response = table.get_item(Key={'id': 0, 'username': 'default'})
    
    item = response["Item"]
    
    return item


# メソッド----------------------------------------------------------
# ユーザー情報取得
def get_user(client, name):
    user = client.get_user(username=name).data
    return user
# 対象ユーザーのツイートを取得
def get_tweets(client, user_id, count):
    # ツイート抽出
    tweets = [
    tweet.data
    for tweet in tweepy.Paginator(
        client.get_users_tweets,
        id = user_id,
        tweet_fields=["created_at","referenced_tweets","in_reply_to_user_id"],
        max_results=100,
    ).flatten(limit=count) #ツイートの取得件数っぽい
    ]
    return tweets

def get_follows(client):
    #フォローユーザーを抽出
    follows = [
    user.data
    for user in tweepy.Paginator(client.get_users_following,
    id = 1481605151224111107,
    max_results=5,).flatten(limit=5)
    ]
    return follows

def reply_tweet(client, username, db_username, screen_name, text):
    if db_username == "default":
        client.create_tweet(text="@" + username + " " + screen_name + text)
    else:
        client.create_tweet(text="@" + username + " " + text)

#関数:　UTCをJSTに変換する
def parse_utc_to_jst(u_time):
    str_time = dateutil.parser.parse(u_time).astimezone(dateutil.tz.gettz('JST'))
    return str_time

# yyyy-mm-dd HH:MM:SS形式にパースする
def parse_yyyymmddHHMMSS(time):
    parse_time = time.strftime('%Y-%m-%d %H:%M:%S')
    return parse_time 
# メソッド----------------------------------------------------------

def lambda_handler(event, context):
    api_key = os.environ.get('TWITTER_API_KEY')
    api_secret = os.environ.get('TWITTER_API_SECRET')
    bearer_token = os.environ.get('TWITTER_BEARER_TOKEN')
    access_token = os.environ.get('TWITTER_ACCESS_TOKEN')
    access_token_secret = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')

    client = tweepy.Client(bearer_token, api_key, api_secret, access_token, access_token_secret)

    # データベースの設定
    progress_bot_table = init_dynamodb()

    # フォローユーザーでループさせる
    for follow in get_follows(client):
        # ユーザー名を取得（@xxxxx)
        username = follow["username"]
        name = follow["name"]
        user = get_user(client, username)
        # ツイートを取得
        tweets = get_tweets(client, user.id, 10)

        for tweet in tweets:
            # リプライ or RTがあったら飛ばす
            if tweet.get("referenced_tweets"):
                continue
            if tweet.get("in_reply_to_user_id"):
                continue

            # ツイート作成日時が ISO8601のタイムゾーンUTCで返ってくるのでJSTにパースする
            print("【" + username + "】")
            now = parse_yyyymmddHHMMSS(datetime.now())
            print(now)
            j_time = parse_utc_to_jst(tweet["created_at"])
            print(parse_yyyymmddHHMMSS(j_time))
            nt = datetime.strptime(str(now),'%Y-%m-%d %H:%M:%S')
            jt = datetime.strptime(str(parse_yyyymmddHHMMSS(j_time)),'%Y-%m-%d %H:%M:%S')
            time_diff = nt - jt

            # base_time = parse_yyyymmddHHMMSS(str(datetime.now().year) + str(datetime.now().month) + str(datetime.now().date) + " 12:00:00")
            print("時間差分：" + str(time_diff))

            #データベースからデータを取得
            progress_bot_item = get_item_to_dynamodb(progress_bot_table, username)
            # ベースタイムセット
            basetime_str = str(time(int(progress_bot_item.get("interval_time")), 00, 00))
            # print("ベースタイム" + str(base_time))
            if time_diff.days > 0:
                reply_tweet(client, username, progress_bot_item.get("username"), name, progress_bot_item.get("replay_text"))
            elif datetime.strptime(str(time_diff),"%H:%M:%S") > datetime.strptime(basetime_str,"%H:%M:%S"):
                reply_tweet(client, username, progress_bot_item.get("username"), name, progress_bot_item.get("replay_text"))
        
            break

    print("---END---")
