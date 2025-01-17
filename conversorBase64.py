import base64

with open("images/foto1.jpg", "rb") as img_file:
    base64_image = base64.b64encode(img_file.read()).decode("utf-8")
print(base64_image)