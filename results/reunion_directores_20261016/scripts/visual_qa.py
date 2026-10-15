from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
O=Path(__file__).resolve().parents[1];files=sorted((O/'figures').glob('*.png'))
for page in range(0,len(files),4):
 canvas=Image.new('RGB',(1800,1160),'#eeeeee');draw=ImageDraw.Draw(canvas)
 for k,p in enumerate(files[page:page+4]):
  im=Image.open(p).convert('RGB');im.thumbnail((890,535));x=(k%2)*900+(900-im.width)//2;y=(k//2)*580+30
  canvas.paste(im,(x,y));draw.text(((k%2)*900+15,(k//2)*580+8),p.stem,fill='black')
 canvas.save(O/'evidence'/('visual_qa_'+str(page//4+1)+'.jpg'),quality=90)
print('Contact sheets:',(len(files)+3)//4)
