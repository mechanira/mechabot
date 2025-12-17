const SamJs = require("sam-js");
const fs = require("fs");

async function synthesizeSAM(text, outputFile, volume = 0.5) {
    try {
        let sam = new SamJs({});
        const rawBuffer = sam.buf8(text);

        const adjustedBuffer = adjustVolume(rawBuffer, volume);

        const wavBuffer = createWavBuffer(adjustedBuffer, 22050, 1, 8);

        fs.writeFileSync(outputFile, wavBuffer);
    }
    catch (e) {
        console.error(e)
    }

}

function adjustVolume(buffer, volume) {
    const adjusted = Buffer.from(buffer);
    for (let i = 0; i < buffer.length; i++) {
        adjusted[i] = Math.round(128 + (buffer[i] - 128) * volume);
    }
    return adjusted;
}

function createWavBuffer(rawBuffer, sampleRate, numChannels, bitDepth) {
    const byteRate = (sampleRate * numChannels * bitDepth) / 8;
    const blockAlign = (numChannels * bitDepth) / 8;
    const dataSize = rawBuffer.length;
    const chunkSize = 36 + dataSize;

    const header = Buffer.alloc(44);
    header.write("RIFF", 0);
    header.writeUInt32LE(chunkSize, 4);
    header.write("WAVE", 8);
    header.write("fmt ", 12);
    header.writeUInt32LE(16, 16);
    header.writeUInt16LE(1, 20);
    header.writeUInt16LE(numChannels, 22);
    header.writeUInt32LE(sampleRate, 24);
    header.writeUInt32LE(byteRate, 28);
    header.writeUInt16LE(blockAlign, 32);
    header.writeUInt16LE(bitDepth, 34);
    header.write("data", 36);
    header.writeUInt32LE(dataSize, 40);

    return Buffer.concat([header, Buffer.from(rawBuffer)]);
}

const text = process.argv[2] || "sam fallback response";
const output_path = process.argv[3] || "sam_output.wav"
const volume = 0.5;
synthesizeSAM(text, output_path, volume);