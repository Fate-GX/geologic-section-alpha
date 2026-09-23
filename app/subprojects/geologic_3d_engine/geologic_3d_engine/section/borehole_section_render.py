"""Render an interpreted section with source borehole stick logs visible."""
from PIL import Image,ImageDraw


COLORS=("#c9b27d","#9aa7ad","#c98762","#d9c6a0","#879a72","#ae8cb8")


def render_borehole_section(section,intake,path,width=1400,height=700,linework=None):
    stations=section["stationsM"];terrain=section["terrainElevationM"];contacts=section["contactElevationsM"]
    if not stations or not contacts:raise ValueError("section geometry is empty")
    left,right,top,bottom=85,width-35,60,height-75
    elevations=list(terrain)+[z for surface in contacts for z in surface]
    for hole in intake["boreholes"]:
        if hole["projectionState"]=="Projected":
            elevations.extend(v["bottomElevationM"] for v in hole["intervals"])
    zlo,zhi=min(elevations)-5,max(elevations)+5
    px=lambda s:left+(right-left)*(s-stations[0])/max(stations[-1]-stations[0],1e-12)
    py=lambda z:bottom-(bottom-top)*(z-zlo)/max(zhi-zlo,1e-12)
    image=Image.new("RGB",(width,height),"white");draw=ImageDraw.Draw(image)
    top_contact=contacts[-1]
    unknown=[(px(s),py(z)) for s,z in zip(stations,terrain)]+[(px(s),py(z)) for s,z in reversed(list(zip(stations,top_contact)))]
    draw.polygon(unknown,fill="#e4e4e4")
    for index,unit in enumerate(section["units"]):
        lo,hi=contacts[index],contacts[index+1]
        polygon=[(px(s),py(z)) for s,z in zip(stations,hi)]+[(px(s),py(z)) for s,z in reversed(list(zip(stations,lo)))]
        draw.polygon(polygon,fill=COLORS[index%len(COLORS)])
        draw.line([(px(s),py(z)) for s,z in zip(stations,hi)],fill="#403a34",width=2)
    draw.line([(px(s),py(z)) for s,z in zip(stations,terrain)],fill="black",width=3)
    for hole in intake["boreholes"]:
        if hole["projectionState"]!="Projected":continue
        x=px(hole["stationM"]);draw.line((x,py(hole["collarElevationM"]),x,py(hole["intervals"][-1]["bottomElevationM"])),fill="#111111",width=5)
        for interval in hole["intervals"]:
            draw.line((x-5,py(interval["bottomElevationM"]),x+5,py(interval["bottomElevationM"])),fill="#111111",width=2)
        draw.text((x+7,py(hole["collarElevationM"])-12),f"{hole['boreholeId']} ({hole['projectionDistanceM']:.0f}m off)",fill="#111111")
    for event in (linework or {}).get("events",[]):
        x=px(event["stationM"]);y=py(event["terrainElevationM"])
        if event["kind"]=="Fault":
            draw.line((x-9,y-14,x+9,y+14),fill="#d00000",width=4);label=f"FAULT {event['featureId']}"
        else:
            draw.ellipse((x-6,y-6,x+6,y+6),outline="#005bbb",width=3);label=f"CONTACT {event['featureId']}"
        draw.text((x+8,y-24),label,fill="#222222")
    draw.rectangle((left,top,right,bottom),outline="black")
    draw.text((20,14),"BOREHOLE-CONSTRAINED LITHOLOGY SECTION — INTERPRETED HYPOTHESIS",fill="#a00000")
    draw.text((20,32),"Black sticks: source logs; coloured surfaces: reviewed correlation + interpolation; not real-region authorized",fill="#222222")
    for i,unit in enumerate(section["units"]):
        x=left+i*210;draw.rectangle((x,bottom+20,x+14,bottom+34),fill=COLORS[i%len(COLORS)],outline="black")
        draw.text((x+20,bottom+18),f"{unit['unitId']}: {unit['normalizedLithology']}",fill="black")
    image.save(path)
    return path
