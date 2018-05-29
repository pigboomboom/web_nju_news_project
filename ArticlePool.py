import time
import logging

from bs4 import BeautifulSoup
from newspaper import Article, news_pool
from praw import Reddit


class MyArticle(Article):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def download(self, *args, **kwargs):
        if self.download_state == 2:
            return
        try:
            super().download(*args, **kwargs)
        except Exception:
            logging.error("Can't download article <%s>." % (self.url))
            self.html = ''
            self.text = ''
            return
        try:
            if self.html == '':
                raise Exception()
            self.parse()
        except Exception:
            # logging.error("Can't parse article <%s>." % (self.url))
            self.text = BeautifulSoup(self.html, 'html5lib').get_text()

    def download_articles(self, *args, **kwargs):
        # adapt to news_pool
        self.download(*args, **kwargs)


class ArticlePool:
    def __init__(self, url_list=None, not_copy=False):
        self.reddit_config = {
            "client_id": "l1IyjBk9uW1EkQ",
            "client_secret": "cMN19pQ-Nnk6bHM9C1BCohHj2gI",
            "user_agent": 'a crawler for reddit, by /u/BlodSide',
            "read_only": True
        }
        self.proxies = {
            'http': 'http:localhost:1080',
            'https': 'http:localhost:1080',
        }
        self.submissions = []
        self.articles = []
        self.reddit = None
        if url_list:
            self.set_articles(url_list)

    def _add_reddit_infos(self):
        for article in self.articles:
            submission = article.reddit_submission
            # basic info
            article.reddit_time_utc = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(submission.created_utc))
            article.reddit_title = submission.title
            article.reddit_subreddit_name = submission.subreddit.display_name
            article.reddit_thumbnail = submission.thumbnail
            article.reddit_fullname = submission.fullname
            # kinds of num
            article.reddit_comments_num = submission.num_comments or 0
            article.reddit_ups = submission.ups or 0
            article.reddit_downs = submission.downs or 0
            article.reddit_score = submission.score or 0

    def set_articles(self, url_list=None):
        if url_list is None:
            if not self.submissions:
                logging.error('Must give a "url_list" or "query_reddit" first.')
                return
            self.articles = [
                MyArticle(url=submission.url, proxies=self.proxies)
                for submission in self.submissions]
            for article, submission in zip(self.articles, self.submissions):
                article.reddit_submission = submission
            self._add_reddit_infos()
        else:
            self.articles = [MyArticle(url=url, proxies=self.proxies) for url in url_list]

    def _init_reddit(self):
        self.submissions = []
        self.reddit = Reddit(**self.reddit_config)

    def query_reddit(self, query, limit=100, is_continue=False):
        # 25 <= limit <= 100
        if self.reddit is None:
            self._init_reddit()
        query += " self:0"
        query_param = {
            "query": query,
            "sort": 'new',
            "syntax": 'plain',
            "time_filter": 'all',
            "params": {
                "limit": limit
            }
        }
        if is_continue and self.submissions:
            query_param["params"]['after'] = self.submissions[-1].fullname
            self.submissions = []
        search_result = self.reddit.subreddit('all').search(**query_param)
        for submission in search_result:
            for ban_url_suffix in ['https://www.reddit.com/r/']:
                if ban_url_suffix == submission.url[:len(ban_url_suffix)]:
                    continue
            self.submissions.append(submission)

    def download_and_parse(self, url_list=None):
        if not self.submissions and url_list is None:
            logging.error('Must give a "url_list" or "query_reddit" first.')
            return
        self.set_articles(url_list)
        news_pool.set(self.articles)
        news_pool.join()

    def get_all_html(self):
        return (article.html for article in self.articles if article.html)

    def get_all_text(self):
        return (article.text for article in self.articles if article.text)


if __name__ == '__main__':
    query = "Jack Ma"
    ap = ArticlePool()
    h_list = [
        "reddit_fullname",
        "reddit_time_utc",
        "url",
        "reddit_ups",
        "reddit_comments_num",
        "reddit_title",
        "text"
    ]
    result = []
    while(len(result) < 500):
        ap.query_reddit(query, is_continue=True)
        if not ap.submissions:
            break
        ap.download_and_parse()
        ap.download_and_parse()
        result += [[(getattr(article, h) or "") for h in h_list] for article in ap.articles if article.text]

    from pandas import ExcelWriter, DataFrame
    writer = ExcelWriter('../jack_ma_plain.xlsx')
    DataFrame(result).to_excel(writer, 'news', header=h_list, index_label="news_id")
    writer.save()
