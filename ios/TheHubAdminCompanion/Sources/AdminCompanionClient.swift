import Foundation

struct CompanionCapabilities: Codable, Equatable {
    let contract: String
    let clientClass: String
    let tokenAudience: String
    let defaultEffect: String
    let capabilities: [String]
    let workstationManagerAccess: Bool

    enum CodingKeys: String, CodingKey {
        case contract, capabilities
        case clientClass = "client_class"
        case tokenAudience = "token_audience"
        case defaultEffect = "default_effect"
        case workstationManagerAccess = "workstation_manager_access"
    }
}

struct FederationStatus: Codable, Identifiable, Equatable {
    let id: String
    let name: String?
    let status: String?
    let updatedDate: String?

    enum CodingKeys: String, CodingKey {
        case id, name, status
        case updatedDate = "updated_date"
    }
}

enum CompanionError: Error {
    case invalidEndpoint
    case rejected(Int)
    case contractViolation
}

struct AdminCompanionClient {
    let baseURL: URL
    let session: URLSession

    init(baseURL: URL = URL(string: "http://127.0.0.1:8000")!, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    private func read<T: Decodable>(_ path: String, as type: T.Type) async throws -> T {
        guard let url = URL(string: path, relativeTo: baseURL) else { throw CompanionError.invalidEndpoint }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("thehub_ios", forHTTPHeaderField: "X-PRII-Client-Class")
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw CompanionError.rejected((response as? HTTPURLResponse)?.statusCode ?? 0)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    func capabilities() async throws -> CompanionCapabilities {
        let value = try await read("/api/admin-companion/capabilities", as: CompanionCapabilities.self)
        guard value.contract == "THEHUB_ADMIN_BOUNDARY/1.0",
              value.clientClass == "thehub_ios",
              value.tokenAudience == "federation-admin-companion",
              value.defaultEffect == "DENY",
              value.workstationManagerAccess == false else {
            throw CompanionError.contractViolation
        }
        return value
    }

    func federationStatus() async throws -> [FederationStatus] {
        try await read("/api/entities/FederationStatus", as: [FederationStatus].self)
    }
}
