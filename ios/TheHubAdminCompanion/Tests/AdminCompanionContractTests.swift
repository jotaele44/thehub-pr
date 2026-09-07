import XCTest
@testable import TheHubAdminCompanion

final class AdminCompanionContractTests: XCTestCase {
    func testCapabilityContractDecodesAsDenyByDefault() throws {
        let data = #"{"contract":"THEHUB_ADMIN_BOUNDARY/1.0","client_class":"thehub_ios","token_audience":"federation-admin-companion","default_effect":"DENY","capabilities":["federation.status.read"],"workstation_manager_access":false}"#.data(using: .utf8)!
        let value = try JSONDecoder().decode(CompanionCapabilities.self, from: data)
        XCTAssertEqual(value.defaultEffect, "DENY")
        XCTAssertFalse(value.workstationManagerAccess)
    }
}
