"""Short-sleeve tees and polos end halfway up the upper arm, not at the elbow (.86.81).

David, 23 Nov 2026: "Where did you get this long sleeves on the t shirts??????? Pls fix they are all normal
length short sleeves", then "Sleeves should be halfway up the upper arm, not to elbow!!!!! For short sleeve tees
and polos. The two missoni zig zag polos are to elbow l[ength]".
Reference he approved the same day, of the Giorgio Armani white tee with the olive linen trousers
(assets/onbody/ceb95c9eb9dca42f.webp): "THIS IS THE CORRECT LENGTH" - fitted sleeves ending mid upper arm,
hem just below the waistband.
The pictures drawn with elbow-length or long sleeves were redrawn; none of them may come back.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ["00672c7bd3362ffd.webp", "01a3d5ebf694cb04.webp", "0236a8977ab31f76.webp", "0a0a01c93683cd7a.webp", "0b67cc6d762d65c4.webp", "0c9e93bb54a411b8.webp", "14615dbb35fdd8ff.webp", "148aafe18cbf1797.webp", "197c326a27d47d08.webp", "1b0203f35abcb1e8.webp", "1bc800fe91c31ad0.webp", "26b5351539816bc7.webp", "2eef8d34c9809f6c.webp", "325473e9bb11adc3.webp", "3869d31d394ea8ad.webp", "3ac294df435b87ec.webp", "3b7ffe71be2d993c.webp", "43801473854e05e2.webp", "4c1a6ed9c13a9376.webp", "563ff1f4f6fd5627.webp", "57c7735394acb3c7.webp", "5d589ce8abfd36c1.webp", "5fb5aa5ffb50a293.webp", "6149e6c378f749f8.webp", "65d3db1938b90f76.webp", "68cd7a59a9e66ec7.webp", "73cc2f57552e0318.webp", "75671141a7101007.webp", "77dbe6c75b74965c.webp", "7bf3825893a18445.webp", "7c3571ec84fccdfd.webp", "7e68b09a828876d9.webp", "7f8b5fc8162f6da3.webp", "81fdeaed39626c62.webp", "8295b49c210cedec.webp", "8633d6b43d3caa17.webp", "89a26e84cbcfb41d.webp", "8bace65a34285932.webp", "91066911870406e0.webp", "931d58de1f64a710.webp", "9643eb1de9f99a62.webp", "971ed0dda6fe9641.webp", "a0558b33583c6462.webp", "a33f4a3e17f89d28.webp", "a51297ffa782e962.webp", "a5e5db961a8b439c.webp", "a6e9e17d86000487.webp", "a7ad5c802f049974.webp", "a86d1d429ee4c020.webp", "aaefd53face8f0ef.webp", "ae5b542691b68715.webp", "b0016abbe4abb1df.webp", "b0d558d575397b7e.webp", "b3247a7d4ca525fb.webp", "bdb03dff2a65571e.webp", "bdc1b017f917f55d.webp", "be01553650033f31.webp", "be200eb687e557d2.webp", "ce12ff0faf3f6fbb.webp", "d27685d52bf94c66.webp", "d2fc7a15dcd725fd.webp", "d3ab3d7125100f64.webp", "d5c5a646fb9e87f6.webp", "d7d9094b521f547f.webp", "d89730bf39db68a3.webp", "d9ba20ffda573091.webp", "f1ff3d2da6074517.webp", "f2721d3b8c8943aa.webp", "f8ddca55c736869f.webp", "fd455d3e0036da8f.webp"]
man = json.loads((ROOT / "assets/onbody/manifest.json").read_text())["r"]
files = {e["f"] for e in man}
back = [f for f in OLD if f in files]
assert not back, ("elbow-length sleeve pictures are listed again", back[:5])
print("Confirmed %d redrawn tee and polo pictures stay at mid-bicep sleeves" % len(OLD))
