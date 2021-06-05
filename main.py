from easysnmp import Session, exceptions
# import plotly.graph_objects as go
# import http.server
# import threading
import requests
import time
import json
import math

# global divhtml


# class Server(http.server.BaseHTTPRequestHandler):
#     def do_GET(self):
#         self.send_response(200)
#         self.send_header("Content-type", "text/html")
#         self.end_headers()
#         self.wfile.write(bytes(divhtml, 'utf8'))


def sumValues(list):
    sum = 0
    for val in list:
        sum += int(val.value)
    return sum


def double_exponential_smoothing(series, alpha, beta):
    result = [series[0]]
    for n in range(1, len(series)+2):
        if n == 1:
            level, trend = series[0], series[1] - series[0]
        if n >= len(series):
            value = result[-1]
        else:
            value = series[n]
        last_level, level = level, alpha*value + (1-alpha)*(level+trend)
        trend = beta*(level-last_level) + (1-beta)*trend
        result.append(level+trend)
    #print(series, result)
    return result


def calcConfidence(values, prediction, rho):
    sumError = int(0)
    for index in range(len(values)):
        sumError += (values[index]-prediction[index])**2
    deviation = math.sqrt(sumError/(len(values)+1))
    return deviation*rho


def snmp():
    try:

        # Setup SNMP
        host = 'localhost'
        ver = 1
        comm = 'public'
        session = Session(hostname=host, version=ver, community=comm)

        # Setup Telegram bot
        with open('credentials.json') as json_file:
            telegram = json.load(json_file)
            token = telegram['bot']
            chatid = telegram['chat']
        url = f'https://api.telegram.org/bot{token}/sendMessage'

        # Initialize data structures and variables
        # x_time = []
        y_cpu = []
        y_cputemp = []
        y_inoct = []
        y_outoct = []
        uptimeOld = 0
        inOctOld = 0
        outOctOld = 0

        firstIter = True

        while True:

            # Get data
            data = ['sysUpTimeInstance', 'ifInOctets.2', 'ifOutOctets.2', 'hrSystem.0']
            values = session.get(data)
            uptimeNew = int(values[0].value)
            inOctNew = int(values[1].value)
            outOctNew = int(values[2].value)
            cputemp = int(values[3].value)
            cpu = session.walk("hrProcessorLoad")
            cpuAvg = sumValues(cpu) / len(cpu)

            # Store new data
            if uptimeNew < uptimeOld:
                print('Computer has been restarted')
                data = {'chat_id': chatid, 'text': f'Computer restarted'}
                requests.post(url, data).json()
                uptimeOld = uptimeNew
                inOctOld = inOctNew
                outOctOld = outOctNew
                time.sleep(300)
                continue
            inOctDiff = inOctNew - inOctOld
            outOctDiff = outOctNew - outOctOld
            if not firstIter:
                y_inoct.append(inOctDiff)
                y_outoct.append(outOctDiff)
            else:
                firstIter = False
            y_cpu.append(cpuAvg)
            y_cputemp.append(cputemp)

            print(f"uptime {uptimeNew}, in {inOctDiff}, out {outOctDiff}, cpu {cpuAvg}, cputemp {cputemp}")

            # Create the figures
            # x_time.append(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
            # fig = go.Figure()
            # fig.add_trace(go.Scatter(x=x_time, y=y_cpu, name="CPU usage"))
            # fig.add_trace(go.Scatter(x=x_time, y=y_cputemp, name="CPU temperature"))
            # fig.update_layout(title='Component usage over time', yaxis_range=[0, 100],
            #                   xaxis_title='Time', yaxis_title='Usage',
            #                   legend_title='Legend', showlegend=True)

            # Create the html code of the figure
            # global divhtml
            # divhtml = fig.to_html()

            # Analyze the data
            if cpuAvg > 80:
                if cpuAvg > 90:
                    data = {'chat_id': chatid, 'text': f'ERROR - CPU Load: {cpuAvg} %'}
                else:
                    data = {'chat_id': chatid, 'text': f'Warning - CPU Load: {cpuAvg} %'}
                requests.post(url, data).json()
            if cputemp > 75:
                if cputemp > 95:
                    data = {'chat_id': chatid, 'text': f'ERROR - CPU Temperature: {cputemp} °C'}
                else:
                    data = {'chat_id': chatid, 'text': f'Warning - CPU Temperature: {cputemp} °C'}
                requests.post(url, data).json()

            # Compare smoothing prediction with real value collected
            alpha= 0.9
            beta = 0.9
            rho = 3
            if len(y_inoct) > 1 and len(y_outoct) > 1:
                # Predict InOct
                predictionIn = double_exponential_smoothing(y_inoct, alpha, beta)
                confidenceIn = calcConfidence(y_inoct, predictionIn, rho)
                #print(confidenceIn)
                lowBound = predictionIn[-3] - confidenceIn
                upBound = predictionIn[-3] + confidenceIn
                if inOctDiff > upBound or inOctDiff < lowBound:
                    data = {'chat_id': chatid, 'text': f'Anomaly detected - InOct: {inOctDiff} bytes'}
                    requests.post(url, data).json()

                # Predict OutOct
                predictionOut = double_exponential_smoothing(y_outoct, alpha, beta)
                confidenceOut = calcConfidence(y_outoct, predictionOut, rho)
                #print(confidenceOut)
                lowBound = predictionOut[-3] - confidenceOut
                upBound = predictionOut[-3] + confidenceOut
                if outOctDiff > upBound or outOctDiff < lowBound:
                    data = {'chat_id': chatid, 'text': f'Anomaly detected - OutOct: {outOctDiff} bytes'}
                    requests.post(url, data).json()

            # Update old variables
            uptimeOld = uptimeNew
            inOctOld = inOctNew
            outOctOld = outOctNew

            time.sleep(5)

    except exceptions.EasySNMPError as error:
        print(error)


if __name__ == "__main__":
    try:
        # webServer = http.server.HTTPServer(('localhost', 7777), Server)
        # threading.Thread(target=webServer.serve_forever, daemon=True).start()
        snmp()
    except KeyboardInterrupt:
        # webServer.server_close()
        print('\nStopping the service')
