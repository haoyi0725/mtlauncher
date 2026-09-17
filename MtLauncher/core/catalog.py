import requests
from core.logger import log

MC_MANIFEST="https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
FABRIC="https://meta.fabricmc.net/v2/versions/loader"
FORGE_MAVEN="https://files.minecraftforge.net/net/minecraftforge/forge/maven-metadata.json"
NEOFORGE_MAVEN="https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"

class VersionCatalog:
    def __init__(self):
        self.session=requests.Session()
        self.session.headers["User-Agent"]="MtLauncher/0.2.0"

    def minecraft_versions(self):
        r=self.session.get(MC_MANIFEST,timeout=15); r.raise_for_status()
        data=r.json()
        # 最新版優先，再列正式 release；snapshot 也保留但排在後面
        releases=[x for x in data["versions"] if x["type"]=="release"]
        snaps=[x for x in data["versions"] if x["type"]!="release"]
        return releases+snaps

    def loader_versions(self,loader,minecraft):
        if loader=="Fabric":
            r=self.session.get(f"{FABRIC}/{minecraft}",timeout=15); r.raise_for_status()
            return [x["loader"]["version"] for x in r.json()]
        if loader=="Forge":
            # Forge Maven metadata API is not uniform across releases; use promotions JSON.
            urls=[
                "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json",
                "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.json"
            ]
            versions=[]
            for u in urls:
                try:
                    r=self.session.get(u,timeout=15); r.raise_for_status(); d=r.json()
                    if "promos" in d:
                        for key,val in d["promos"].items():
                            if key.startswith(minecraft+"-"): versions.append(val)
                    if "versioning" in d:
                        versions += [x["version"] for x in d["versioning"].get("versions",[])]
                    if versions: break
                except Exception: pass
            return sorted(set(versions),reverse=True)
        if loader=="NeoForge":
            # NeoForge Maven metadata is XML; filter versions compatible by major MC family.
            import xml.etree.ElementTree as ET
            r=self.session.get(NEOFORGE_MAVEN,timeout=15); r.raise_for_status()
            root=ET.fromstring(r.text)
            vals=[x.text for x in root.findall(".//version") if x.text]
            # NeoForge 20.x -> MC 1.20.2/1.20.4, 21.x -> 1.21.x, etc.
            major="21." if minecraft.startswith("1.21") else ("20." if minecraft.startswith("1.20") else None)
            if major: vals=[v for v in vals if v.startswith(major)]
            return sorted(set(vals),reverse=True)
        return []
