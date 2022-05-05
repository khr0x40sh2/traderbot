from webull import webull
from os.path import exists
import json
import btalib	#performs RSI calculation
import time
import datetime

import config	#config.py should house login credentials if needed
from db import mysqlConn
from slack import WebClient
from slackBot import SlackBot #slack notification plugin
from config import *


def loginWB(login, pw, wb):
    if exists('webull_credentials.json'):
        fh = open('webull_credentials.json', 'r')
        credential_data = json.load(fh)
        fh.close()

        wb._refresh_token = credential_data['refreshToken']
        wb._access_token = credential_data['accessToken']
        wb._token_expire = credential_data['tokenExpireTime']
        wb._uuid = credential_data['uuid']

        n_data = wb.refresh_login()

        credential_data['refreshToken'] = n_data['refreshToken']
        credential_data['accessToken'] = n_data['accessToken']
        credential_data['tokenExpireTime'] = n_data['tokenExpireTime']

        file = open('webull_credentials.json', 'w')
        json.dump(credential_data, file)
        file.close()

        # important to get the account_id
    else:
        print(wb.get_mfa(login))
        mfa_code = input("MFA CODE:")
        secQ = wb.get_security(login)
        print(secQ)
        answer = input("Answer:")
        question_id = secQ[0]["questionId"]
        data = wb.login(login, pw, 'PythonTest', mfa_code, question_id, answer)
        try:
            file = open('webull_credentials.json', 'w')
            json.dump(data, file)
            file.close()
        except Exception as e:
            print("[!] Error occurred: \n{}".format(e))
            pass

def logToFile(filename, string):
    f = open(filename, 'a+')
    f.writelines(string+"\n")
    f.close()

def insertintoDB_entry(db, symb, option_name, price, strat):
    try:
        mycursor = db.cursor(buffered=True)
        now = datetime.datetime.now()
        sql = "INSERT INTO held_options (symbol,option_name, entry, entry_timestamp, strategy) VALUES (%s,%s,%s,%s, %s)"
        val = (symb, option_name, price,str(now), strat)
        print(val)
        mycursor.execute(sql, val)
        db.commit()
        return mycursor.lastrowid
    except TypeError as e:
        print("[!] There was an error inserting purchased option\n{}".format(e))
        return -1

def insertintoDB_exit(price, option_id, reason):
    try:
        mycursor = db.cursor()
        now = datetime.datetime.now()
        sql = "UPDATE held_options SET exit_price = %s, exit_timestamp = %s, reason = %s WHERE id = %s"
        val = (price, str(now), reason, option_id)
        print(val)
        mycursor.execute(sql, val)
        db.commit()
        return True
    except TypeError as e:
        print("[!] There was an error inserting sold option\n{}".format(e))
        return False

def slackCallout(slackC, message):
    slackC.send_response(message, slackC.channel)

def isTradingDay(currenthour):
    if currenthour > 9 and currenthour < 16:
        return True
    else:
        return False

###ALGO stuff
def RSIcrossover(rsi1, rsi2):
    if rsi1 >= 50 and rsi2 < 50:
        return True, True #return RSIx50, call
    elif rsi1 <= 50 and rsi2 > 50:
        return True, False #return RSIx50, put
    else:
        return False, False

def GetTargetOptions(wb, symb, call, maxAsk, minAsk):
    try:
        optdates = wb.get_options_expiration_dates(symb)
        """
        TODO:
        ----
        Find nearest and second nearest date if we are within 2 days of close
        Find strikes within 2 of current price
        """
        for optdate in optdates:
            quote = wb.get_quote(symb)
            currentPrice = quote["close"]
            if _debug_:
                print(currentPrice)
            contracts = wb.get_options(stock=symb, expireDate=optdate['date'], direction='calls')
            validOptions = []
            for i in range(len(contracts)):
                if call:
                    optionStr = "call"
                else:
                    optionStr = "put"
                if float(contracts[i]["strikePrice"]) >= float(currentPrice):
                    validOptions.append(contracts[i][optionStr])
                    try:
                        validOptions.append(contracts[i-1][optionStr])
                        validOptions = validOptions[::-1]
                        idx = 1 if call else -2
                        validOptions.append(contracts[i+idx][optionStr])
                        break
                    except:
                        pass
            if not call:
                validOptions = validOptions[::-1] #flip order for puts
            if len(validOptions):
                found = False
                for vOS in validOptions:
                    ask = float(vOS["askList"][0]["price"])
                    bid = float(vOS["bidList"][0]["price"])
                    if _debug_:
                        print("[!]\tBid\t\tAsk \t{}\n\t{}\t{}".format(vOS["symbol"],
                                                          bid,ask))
                    if float(ask) < minAsk or float(ask) > maxAsk:
                        if float(ask) < minAsk:
                            print("[!] Ask is below purchase threshold of ${:,.2f} (${:,.2f})\n\tLooking for another strike...".format(float(minAsk), float(ask)))
                            break
                        if float(ask) > maxAsk:
                            print("[!] Ask is above purchase threshold of ${:,.2f} (${:,.2f})\n\tLooking for another strike...".format(float(maxAsk), float(ask)))
                            #skip to next strike
                    else:
                        #suitable strike found, let's use it
                        targetOpt = vOS
                        found = True
                        if _debug_:
                            print("[!] Suitable strike found @ {}".format(float(ask)))
                        break
                if found:
                    break
        if not found:
            print("[!] No suitable strikes found!\n\tAdjust settings or try later...")
            return None
        return targetOpt
    except Exception as e:
        print("[!] Error pulling data, trying again 60 seconds\n{}".format(e))
        logToFile(filename, "{} - Error pulling data, trying again 60 seconds\n{}".format(datetime.datetime.now(), e))
        return None

def purchaseTargetOption(wb, targetOpt,buy,callorPut, threshold,quantity):
    filled = False
    ask = targetOpt["askList"][0]["price"]
    if _debug_:
        success = 'success'
    if buy:
        #notionally fill at ASK - we are going to try and split the spread later
        price = ask
        """
        TO DO:
        Fill at ask for now - future would look to try haggle in the spread somewhere
        """
        # insert stub from tda/webull
        #place_order_option(self, optionId=None, lmtPrice=None, stpPrice=None, action=None, orderType='LMT', enforce='DAY', quant=0)
        #success = wb.place_order_option(optionId=targetOpt["symbol"], action='buy', orderType='MKT', quant=quantity)
        if "success" in str(success).lower():
            if _debug_:
                print("[!] Purchased {} @ {}".format(datetime.datetime.now(),targetOpt['symbol'], price))
            logToFile(filename, "{} - Purchased {} @ {}".format(datetime.datetime.now(),targetOpt['symbol'], price))
            ##DB entry ### insertintoDB_entry(db, symb, option_name, price, strat) # using only RSIx50 for now
            targetOpt['dbID'] = insertintoDB_entry(db, symb, targetOpt['symbol'], price, "RSIx50")
            #price needs to be updated to match filled price in the json
            #price = success["price"]
            filled = True
    else:
        price = ask
        # bid = targetOpt["bidList"][0]["price"]
        newTarget = wb.get_options_by_strike_and_expire_date(stock=symb, expireDate=targetOpt['expireDate'], strike=targetOpt['strikePrice'], direction=targetOpt['direction'])
        direction = "call" if callorPut else "put"
        bid = newTarget[0][direction]['bidList'][0]['price']
        percentage = float(bid) / float(price) - 1
        if threshold == 0:
            # place_order_option(self, optionId=None, lmtPrice=None, stpPrice=None, action=None, orderType='LMT', enforce='DAY', quant=0)
            # success = wb.place_order_option(optionId=targetOpt["symbol"], action='sell', orderType='MKT', quant=quantity)
            if 'success' in str(success).lower():
                if _debug_:
                    print("[!] EoD reached... selling regardless of profit/loss @ {},\n\t{:.0%} profit".format(bid, percentage))
                logToFile(filename, "{} - EoD reached... selling regardless of profit/loss @ {},{:.0%} profit".format(
                    datetime.datetime.now(), bid, percentage))
                #below is a boolean, we will put the check in later
                insertintoDB_exit(bid, targetOpt['dbID'], "EoD reached")
                # price = success["price"] #this is "bid" while we are 'paper' trading
                filled = True
        else:
            if float(percentage) >= float(threshold) or float(percentage) <= float(-1*float(threshold)):
                # ok, let's sell for profit or loss lulz
                # place_order_option(self, optionId=None, lmtPrice=None, stpPrice=None, action=None, orderType='LMT', enforce='DAY', quant=0)
                # success = wb.place_order_option(optionId=targetOpt["symbol"], action='buy', orderType='MKT', quant=quantity)
                if 'success' in str(success).lower():

                    if _debug_:
                        print("[!] Current bid price is {}\n\tselling for a {:.0%} profit/loss".format(bid, percentage))

                    reason = "Threshold reached, {:.0%} profit".format(percentage) if percentage > 0 else "Stop Loss hit, {:.0%} loss".format(percentage)
                    logToFile(filename,"{} - Current bid price is {}, selling for a {:.0%} profit/loss".format(datetime.datetime.now(),bid, percentage))
                    insertintoDB_exit(bid,targetOpt['dbID'], reason=reason)
                    #price = success["price"]
                    filled = True
            else:
                if _debug_:
                    print("[!] Current bid price is {}\n\tselling now would be a {:.0%} profit/loss".format(bid, ((float(bid)/float(price)-1))))
                #logToFile(filename,"{} - Current bid price is {}, selling now would be a {:. 0%} profit".format(datetime.datetime.now(),bid, (float(bid)/float(price))-1))
    return targetOpt, price, filled

if __name__ == '__main__':
    #debug Flag
    _debug_ = True
    #log file
    filename = 'logs/{}_{}.txt'.format(symb, time.time())

    #option variables (min max ask, qty)
    qty = 0
    maxAsk = 2.0
    minAsk = 0.5

    # if _debug_:
    #    print(wb.get_account())
    currenthour = datetime.datetime.now().hour

    ### debugging stuff
    paper = True	#future flag to ensure we are strickly paper trading
    waitToCall = False
    waitToPut = False
    openToTrade = False
    holdCall = False
    holdPut = False
    sellThreshold = .10
    strike = None
    #######

    ##webull stuff
    wb = webull()
    symb= config.symb
    login = config.login
    pw = config.pw
    loginWB(login, pw, wb) ##this will become a bool check
    wb.get_account_id()
    wb.get_trade_token(config.trade_pin)

    #Slack stuff, uncomment and configure for slack notifications
    #SLACK_TOKEN="<insert slack token here>"
    #slackC = WebClient(token=SLACK_TOKEN)
    #slack_bot = SlackBot("<insert channel here>")

    #Database stuff
    try:
        db = mysqlConn.connect(None)
    except Exception as e:
        print("[!] Error connecting to mysql database, check connects, and try again.\n{}".format(e))

    while True:
        try:
            data = wb.get_bars(stock=symb, count=60, extendTrading=1)
            rsi = btalib.rsi(data)
            data['rsi'] = rsi.df
            dataLast = data.iloc[-1]
            dataLast2 = data.iloc[-2]

            if _debug_:
                print("[!] Debug RSI Values {}\tfrom\t{} ".format(dataLast['rsi'],dataLast2['rsi']))
			logToFile(filename, "{} Debug RSI Values {}\tfrom\t{} ".format(datetime.datetime.now(), dataLast['rsi'],dataLast2['rsi']))

            #RSI cross check
            RSIx50, callorPut = RSIcrossover(float(dataLast['rsi']), float(dataLast2['rsi']))

            if RSIx50 and not (holdCall or holdPut):
                if not waitToCall:
                    waitToCall = False if waitToCall else (True if callorPut else False)
                if not waitToPut:
                    waitToPut = False if waitToPut else (True if not callorPut else False)
                if _debug_:
                    msg = "[!] RSI above 50, at @ {} - waiting for RSI below 30 event to enter call".format(dataLast['rsi'])\
                        if callorPut else "[!] RSI below 50, at @ {} - waiting for RSI above 70 event to enter put".format(dataLast['rsi'])
                    print(msg)
                logToFile(filename, "{} - {} ".format(datetime.datetime.now(), msg))


            if waitToPut or waitToCall or holdCall or holdPut:
                if waitToCall or waitToPut:
                    ##the below are broken out for debugging purposes. I am aware there is a more pythonic way to do this.
                    if waitToCall:
                        if float(dataLast['rsi']) >= float(dataLast2['rsi'])*1.2:
                            #cancel downtrend
                            print("[+] Downturn trend cancelled because rsi values went from {} to {} (a {:.0%} increase)".\
                                  format(dataLast2['rsi'], dataLast['rsi'], (float(dataLast['rsi'])/float(dataLast2['rsi']))-1))
                            waitToCall=False
                        else:
                            if (dataLast['rsi'] <= 30.0):
                                print("[+] Potential entry point, attempting to fill NTM call on {}".format(symb))
                                strike = GetTargetOptions(wb, symb, True, maxAsk, minAsk)
                                if len(strike):
                                    strike, price, filled = purchaseTargetOption(wb, strike, True, None, sellThreshold, qty)
                                    if filled:
                                        message = "{} - Purchased {} @ {}".format(datetime.datetime.now(), strike['symbol'],
                                                                                  price)
                                        logToFile(filename, message)
                                        #Slack stuff
										"""
										try:
                                            mess = slack_bot.get_message_payload(message)
                                            slackC.chat_postMessage(**mess)
                                        except:
                                            pass
										"""
                                        holdCall = True
                                        waitToCall = False
                                    else:
                                        print("[!] Could not fill {} @ {}, trying again later...".format())

                    if waitToPut:
                        if float(dataLast['rsi']) <= float(dataLast2['rsi']) * 0.8:
                            # cancel downtrend
                            print("[+] Upward trend cancelled because rsi values went from {} to {} (a {:.0%} change)".\
                              format(dataLast2['rsi'], dataLast['rsi'],
                                     (float(dataLast['rsi']) / float(dataLast2['rsi'])) - 1))
                            waitToPut = False
                        if (dataLast['rsi'] >= 70.0):
                            print("[+] Potential entry point, attempting to fill NTM put on {}".format(symb))
                            strike = GetTargetOptions(wb, symb, False, maxAsk, minAsk)
                            if len(strike):
                                strike, price, filled = purchaseTargetOption(wb, strike, True, None, sellThreshold, qty)
                                if filled:
                                    message = "{} - Purchased {} @ {}".format(datetime.datetime.now(),
                                                                              strike['symbol'],
                                                                              price)
                                    logToFile(filename, message)
                                    #Slack stuff, uncomment to use
									"""
									try:
                                        mess = slack_bot.get_message_payload(message)
                                        slackC.chat_postMessage(**mess)
                                    except:
                                        pass
									"""
                                    holdPut = True
                                    waitToPut = False
                                else:
                                    print("[!] Could not fill {} @ {}, trying again later...".format())

                if holdCall or holdPut:
                    if datetime.datetime.now().time() > datetime.time(15, 45, 00):
                        sellThr = 0
                        if _debug_:
                            print("[!] Selling open options as it is time to close up!")
                    else:
                        sellThr = sellThreshold
                    strike, price, filled = purchaseTargetOption(wb, strike, False, holdCall, sellThr, qty)
                    if filled:
                        # At the moment, can only hold one or the other. Eventually this will have to be worked out if
                        # ever the algo holds both
                        holdCall = False
                        holdPut = False
                        time.sleep(30)
                time.sleep(10)
            else:
                time.sleep(10)
        except Exception as e:
            print("[!] Error pulling data, trying again 60 seconds\n{}".format(e))
            logToFile(filename,"{} - Error pulling data, trying again 60 seconds\n{}".format(datetime.datetime.now(),e))
            time.sleep(1)
