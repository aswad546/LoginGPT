from modules.analyzers.landscape_analyzer import LandscapeAnalyzer
from modules.analyzers.login_trace_analyzer import LoginTraceAnalyzer
from modules.analyzers.wildcard_receiver_analyzer import WildcardReceiverAnalyzer
from modules.analyzers.privacy_analyzer import PrivacyAnalyzer


ANALYZER = {
    "landscape_analysis": LandscapeAnalyzer,
    "login_trace_analysis": LoginTraceAnalyzer,
    "wildcard_receiver_analysis": WildcardReceiverAnalyzer,
    "privacy_analysis": PrivacyAnalyzer
}
