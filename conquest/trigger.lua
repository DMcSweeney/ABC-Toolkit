
args = {}
for word in command_line:gmatch("%S+") do table.insert(args, word) end

local url = "https://backend:5001/api/conquest/handle_trigger?series_uid="..args[1].."\\&study_uid="..args[2].."\\&patient_id="..args[3].."\\&modality="..args[4].."\\&manufacturer="..args[5]

os.execute("curl -k -X POST "..url )