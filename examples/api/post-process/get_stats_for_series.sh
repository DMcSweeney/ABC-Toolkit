curl --request POST\
    --header "Content-Type: application/json"\
    --data '{"_id": "1.3.6.1.4.1.5962.99.1.815501911.1809853723.1675852780119.1534.0", "project": "testME", "format": "metric"}'\
    http://localhost:5001/api/post_process/get_stats_for_series