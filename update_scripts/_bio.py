[1mdiff --git a/update_stocks_bio.py b/update_stocks_bio.py[m
[1mindex 0e856f7..5bfd9c0 100644[m
[1m--- a/update_stocks_bio.py[m
[1m+++ b/update_stocks_bio.py[m
[36m@@ -1,6 +1,7 @@[m
 # Этот скрипт обновляет необходимые данные (ищет товар по Code,  меняет в нём price и  stock) на сервере ,[m
 # путём отправки их на https://pospro.kz/data_stocks_bio.php[m
[31m-[m
[32m+[m[32m# путём отправки их на https://pospro.kz/dublicate_delete.php[m
[32m+[m[32m#[m[41m [m
 import requests[m
 import sqlite3[m
 import time[m
[36m@@ -50,7 +51,7 @@[m [mdef chunk_list(data, chunk_size):[m
 [m
 def send_stock_with_price_to_server(stock_data, chunk_size=10):[m
     global response[m
[31m-    url = "https://pospro.kz/data_stocks_bio.php"[m
[32m+[m[32m    url = "https://pospro.kz/dublicate_delete.php"[m
     total_chunks = ceil(len(stock_data) / chunk_size)[m
     chunk_index = 1[m
 [m
