#!/usr/bin/env swift

import Foundation

guard CommandLine.arguments.count >= 2 else {
    fputs("usage: validate_fcpxml.swift <file.fcpxml> [FCPXML.dtd]\n", stderr)
    exit(2)
}

let xmlURL = URL(fileURLWithPath: CommandLine.arguments[1])

do {
    let document = try XMLDocument(contentsOf: xmlURL, options: [])
    guard
        let root = document.rootElement(),
        root.name == "fcpxml",
        let version = root.attribute(forName: "version")?.stringValue
    else {
        throw NSError(
            domain: "FCPXMLValidator",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "Missing fcpxml root or version"]
        )
    }

    let dtdURL: URL
    if CommandLine.arguments.count >= 3 {
        dtdURL = URL(fileURLWithPath: CommandLine.arguments[2])
    } else {
        let dtdName = "FCPXMLv\(version.replacingOccurrences(of: ".", with: "_")).dtd"
        let applicationNames = try FileManager.default.contentsOfDirectory(
            atPath: "/Applications"
        ).filter {
            $0.hasPrefix("Final Cut Pro") && $0.hasSuffix(".app")
        }
        let candidates = applicationNames.map {
            URL(fileURLWithPath: "/Applications")
                .appendingPathComponent($0)
                .appendingPathComponent(
                    "Contents/Frameworks/Interchange.framework/Versions/A/Resources"
                )
                .appendingPathComponent(dtdName)
        }.filter {
            FileManager.default.fileExists(atPath: $0.path)
        }
        guard let found = candidates.sorted(by: { $0.path < $1.path }).first else {
            throw NSError(
                domain: "FCPXMLValidator",
                code: 2,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        "No installed Final Cut Pro DTD found for FCPXML \(version)"
                ]
            )
        }
        dtdURL = found
    }

    let dtd = try XMLDTD(contentsOf: dtdURL, options: [])
    dtd.name = "fcpxml"
    document.dtd = dtd
    try document.validate()
    print("Apple FCPXML \(version) DTD validation: OK")
    print("DTD: \(dtdURL.path)")
} catch {
    fputs("FCPXML validation failed: \(error.localizedDescription)\n", stderr)
    exit(1)
}
