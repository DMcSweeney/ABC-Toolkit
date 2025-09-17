-- local socket = require("socket")
-- local https = require("ssl")

-- local params = {
--   mode = "client",
--   protocol = "tlsv1",
--   key = "/ssl/cert.key",
--   certificate = "/ssl/cert.crt",
--   verify = "peer",
--   options = "all"
-- }

-- local conn = socket.tcp()
-- conn:connect('backend', "5001")
-- conn, more = ssl.wrap(conn, params)
-- conn:dohandshake()


-- args = {}
-- for word in command_line:gmatch("%S+") do table.insert(args, word) end
--     if conn then
--         conn:send("POST /api/conquest/handle_trigger?series_uid="..args[1].."&study_uid="..args[2].."&patient_id="..args[3].."&modality="..args[4].."&manufacturer="..args[5].." HTTP/1.1\r\n\r\n")
--         conn:close()
--end

local service = os.getenv('HOST_IP')
local port = os.getenv('BACKEND_PORT')

args = {}
for word in command_line:gmatch("%S+") do table.insert(args, word) end

local url = "https://"..service..":"..port.."/api/conquest/handle_trigger?series_uid="..args[1].."\\&study_uid="..args[2].."\\&patient_id="..args[3].."\\&modality="..args[4].."\\&manufacturer="..args[5]

os.execute("curl -k -X POST "..url )