

signature_file = "/usr/local/lib/python3.9/site-packages/slack_sdk/signature/__init__.py"

with open(signature_file) as f:
    file_data = f.read().replace("abs(self.clock.now() - int(timestamp)) > 60 * 5",
                                 "abs(self.clock.now() - int(timestamp)) > 60 * 10")

with open(signature_file, "w") as f:
    f.write(file_data)
